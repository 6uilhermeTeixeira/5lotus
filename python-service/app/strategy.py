from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import fmean, pstdev

from .config import Settings
from .schemas import CandleSnapshot, DecisionAction, DecisionRequest, DecisionResponse, FlowSnapshot, RiskCheck


@dataclass
class Setup:
    action: DecisionAction
    setup_type: str
    entry: float
    stop: float
    partial: float
    target: float
    stop_points: float
    flow_mode: str
    ema20: float
    atr14: float


_flow_windows: dict[str, deque[tuple[float, float]]] = defaultdict(lambda: deque(maxlen=60))


def _ema(values: list[float], period: int = 20) -> float:
    result = values[0]
    alpha = 2 / (period + 1)
    for value in values[1:]:
        result += alpha * (value - result)
    return result


def _atr(candles: list[CandleSnapshot], period: int = 14) -> float:
    ranges = [max(c.high - c.low, abs(c.high - candles[i - 1].close), abs(c.low - candles[i - 1].close)) for i, c in enumerate(candles[-period:], len(candles) - period)]
    return fmean(ranges)


def _z(value: float, values: list[float]) -> float:
    deviation = pstdev(values)
    return 0.0 if deviation == 0 else (value - fmean(values)) / deviation


def _flow_metrics(flow: FlowSnapshot) -> tuple[float, float] | None:
    bids = sum(level.volume for level in flow.book if level.side == "bid")
    asks = sum(level.volume for level in flow.book if level.side == "ask")
    total_book = bids + asks
    total_ticks = flow.up_volume + flow.down_volume
    if total_book <= 0 or total_ticks <= 0:
        return None
    return ((bids - asks) / total_book, (flow.up_volume - flow.down_volume) / total_ticks)


def _record_flow(request: DecisionRequest) -> tuple[tuple[float, float] | None, deque[tuple[float, float]] | None]:
    if request.flow is None:
        return None, None
    metrics = _flow_metrics(request.flow)
    if metrics is None:
        return None, None
    key = request.bot_id or request.symbol
    window = _flow_windows[key]
    window.append(metrics)
    return metrics, window


def _flow_confirmation(metrics: tuple[float, float] | None, window: deque[tuple[float, float]] | None, action: DecisionAction) -> tuple[bool, str]:
    if metrics is None or window is None:
        return False, "flow_unavailable"
    if len(window) < window.maxlen:
        return False, "flow_warmup"
    book_z = _z(metrics[0], [item[0] for item in window])
    tick_z = _z(metrics[1], [item[1] for item in window])
    direction = 1 if action == DecisionAction.BUY else -1
    if direction * book_z >= 1 and direction * tick_z >= 1:
        return True, "aggression"
    if direction * book_z >= 1 and direction * tick_z <= -1:
        return True, "absorption"
    return False, "flow_not_confirmed"


def _position_size(balance: float, risk_pct: float, stop_points: float, value_per_point: float) -> float:
    return (balance * risk_pct / 100) / (stop_points * value_per_point)


def _setup(request: DecisionRequest) -> Setup | None:
    candles = request.candles
    if len(candles) < 23:
        return None
    closes = [c.close for c in candles]
    ema20 = _ema(closes[-21:-1])
    previous_ema = _ema(closes[-22:-2])
    atr14 = _atr(candles[:-1])
    current, previous = candles[-1], candles[-2]
    tolerance, extension = atr14 * .15, atr14 * .5
    bullish = current.close > ema20 and ema20 > previous_ema
    bearish = current.close < ema20 and ema20 < previous_ema
    if not bullish and not bearish:
        return None
    action = DecisionAction.BUY if bullish else DecisionAction.SELL
    pullback = (current.low <= ema20 + tolerance and current.close > ema20) if bullish else (current.high >= ema20 - tolerance and current.close < ema20)
    outside_inside = (previous.close < ema20 - extension and current.close > ema20) if bullish else (previous.close > ema20 + extension and current.close < ema20)
    if not pullback and not outside_inside:
        return None
    stop = (min(current.low, previous.low) - atr14 * .25) if bullish else (max(current.high, previous.high) + atr14 * .25)
    entry = request.ask if bullish else request.bid
    points = abs(entry - stop) / request.point_size
    if points <= 0:
        return None
    partial_points, target_points = points, points * 2
    partial = entry + partial_points * request.point_size if bullish else entry - partial_points * request.point_size
    target = entry + target_points * request.point_size if bullish else entry - target_points * request.point_size
    return Setup(action, "pullback" if pullback else "outside_inside", entry, stop, partial, target, points, "", ema20, atr14)


def evaluate_decision(request: DecisionRequest, settings: Settings) -> DecisionResponse:
    flow_metrics, flow_window = _record_flow(request)
    setup = _setup(request)
    checks = [
        RiskCheck(name="symbol_match", passed=request.symbol.upper() == settings.default_symbol.upper(), detail=f"expected={settings.default_symbol}"),
        RiskCheck(name="timeframe_match", passed=request.timeframe.upper() == settings.default_timeframe.upper(), detail=f"expected={settings.default_timeframe}"),
        RiskCheck(name="spread_limit", passed=request.spread_points <= settings.max_spread_points, detail=f"max={settings.max_spread_points}"),
        RiskCheck(name="fimath_setup", passed=setup is not None, detail="ema20 pullback/outside-inside"),
    ]
    if not all(check.passed for check in checks[:3]):
        return DecisionResponse(action=DecisionAction.HOLD, reason="market_filter_mismatch", risk_checks=checks)
    if setup is None:
        return DecisionResponse(action=DecisionAction.HOLD, reason="fimath_setup_not_confirmed", risk_checks=checks)
    flow_ok, flow_mode = _flow_confirmation(flow_metrics, flow_window, setup.action)
    checks.append(RiskCheck(name="flow_confirmation", passed=flow_ok, detail=flow_mode))
    if not flow_ok:
        return DecisionResponse(action=DecisionAction.HOLD, reason=flow_mode, risk_checks=checks)
    size = round(_position_size(request.account.balance, settings.risk_per_trade_pct, setup.stop_points, request.value_per_point_per_lot), 2)
    executable = settings.fimath_mode == "live" and settings.enable_live_decisions
    checks.append(RiskCheck(name="fimath_live_enabled", passed=executable, detail=f"mode={settings.fimath_mode}"))
    return DecisionResponse(
        action=setup.action if executable else DecisionAction.HOLD,
        reason="fimath_validated" if executable else "fimath_shadow_signal",
        size=size if executable else 0.0,
        risk_amount=round(request.account.balance * settings.risk_per_trade_pct / 100, 2),
        entry_price=setup.entry, stop_loss_price=setup.stop, take_profit_price=setup.target,
        stop_loss_points=round(setup.stop_points, 2), take_profit_points=round(setup.stop_points * 2, 2),
        partial_take_profit_price=setup.partial, final_take_profit_price=setup.target,
        partial_close_pct=settings.fimath_partial_pct, move_stop_to_breakeven=True,
        risk_checks=checks,
        metadata={"strategy_profile": settings.strategy_profile, "setup_type": setup.setup_type, "flow_mode": flow_mode, "ema20": round(setup.ema20, 5), "atr14": round(setup.atr14, 5), "suggested_size": size, "suggested_action": setup.action.value},
    )
