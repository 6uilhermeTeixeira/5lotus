from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    ema50: float | None = None
    breakout_level: float | None = None
    rsi14: float | None = None
    bollinger_upper: float | None = None
    bollinger_lower: float | None = None


@dataclass
class FlowSample:
    timestamp_utc: datetime
    book_imbalance: float
    tick_imbalance: float


@dataclass
class FlowAnalysis:
    ready: bool
    confirmed: bool
    contradicted: bool
    status: str
    book_z: float | None = None
    tick_z: float | None = None
    score: float | None = None


_flow_windows: dict[str, deque[FlowSample]] = defaultdict(deque)
_setup_cache: dict[str, tuple[datetime, Setup | None]] = {}


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


def _rsi(values: list[float], period: int = 14) -> float:
    changes = [current - previous for previous, current in zip(values[-period - 1:-1], values[-period:])]
    average_gain = fmean(max(change, 0.0) for change in changes)
    average_loss = fmean(max(-change, 0.0) for change in changes)
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _flow_metrics(flow: FlowSnapshot) -> tuple[float, float] | None:
    bids = sum(level.volume for level in flow.book if level.side == "bid")
    asks = sum(level.volume for level in flow.book if level.side == "ask")
    total_book = bids + asks
    total_ticks = flow.up_volume + flow.down_volume
    if total_book <= 0 or total_ticks <= 0:
        return None
    return ((bids - asks) / total_book, (flow.up_volume - flow.down_volume) / total_ticks)


def _record_flow(request: DecisionRequest, window_seconds: int) -> deque[FlowSample] | None:
    if request.flow is None:
        return None
    metrics = _flow_metrics(request.flow)
    if metrics is None:
        return None
    key = request.bot_id or request.symbol
    window = _flow_windows[key]
    window.append(FlowSample(request.timestamp_utc, metrics[0], metrics[1]))
    cutoff = request.timestamp_utc - timedelta(seconds=window_seconds)
    while window and window[0].timestamp_utc < cutoff:
        window.popleft()
    return window


def _flow_analysis(
    window: deque[FlowSample] | None,
    action: DecisionAction,
    window_seconds: int,
    min_samples: int,
    z_threshold: float,
) -> FlowAnalysis:
    if window is None:
        return FlowAnalysis(False, False, False, "flow_unavailable")
    history = list(window)
    if len(history) <= min_samples:
        return FlowAnalysis(False, False, False, "flow_warmup")
    elapsed = (history[-1].timestamp_utc - history[0].timestamp_utc).total_seconds()
    if elapsed < window_seconds * 0.8:
        return FlowAnalysis(False, False, False, "flow_warmup")
    current, baseline = history[-1], history[:-1]
    book_z = _z(current.book_imbalance, [item.book_imbalance for item in baseline])
    tick_z = _z(current.tick_imbalance, [item.tick_imbalance for item in baseline])
    direction = 1 if action == DecisionAction.BUY else -1
    directed_book, directed_tick = direction * book_z, direction * tick_z
    score = (directed_book + directed_tick) / 2
    confirmed = directed_book >= z_threshold and abs(directed_tick) >= z_threshold
    contradicted = directed_book <= -z_threshold and directed_tick <= -z_threshold
    if contradicted:
        status = "flow_contradiction"
    elif confirmed and directed_tick >= z_threshold:
        status = "aggression"
    elif confirmed:
        status = "absorption"
    else:
        status = "flow_neutral"
    return FlowAnalysis(True, confirmed, contradicted, status, book_z, tick_z, score)


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


def _setup_for_candle(request: DecisionRequest) -> Setup | None:
    if not request.candles:
        return None
    key = f"{request.bot_id or request.symbol}:{request.symbol}:{request.timeframe}"
    candle_timestamp = request.candles[-1].timestamp_utc
    cached = _setup_cache.get(key)
    if cached and cached[0] == candle_timestamp:
        return cached[1]
    setup = _setup(request)
    _setup_cache[key] = (candle_timestamp, setup)
    return setup


def _momentum_atr_setup(request: DecisionRequest) -> Setup | None:
    candles = request.candles
    if len(candles) < 52:
        return None
    closes = [candle.close for candle in candles]
    current = candles[-1]
    ema20 = _ema(closes[-20:])
    previous_ema20 = _ema(closes[-21:-1])
    ema50 = _ema(closes[-50:])
    atr14 = _atr(candles, 14)
    previous = candles[-13:-1]
    upper_breakout = max(candle.high for candle in previous)
    lower_breakout = min(candle.low for candle in previous)
    bullish = current.close > upper_breakout and current.close > ema20 and ema20 > ema50 and ema20 > previous_ema20
    bearish = current.close < lower_breakout and current.close < ema20 and ema20 < ema50 and ema20 < previous_ema20
    if not bullish and not bearish:
        return None
    action = DecisionAction.BUY if bullish else DecisionAction.SELL
    entry = request.ask if bullish else request.bid
    stop_distance = atr14 * 1.2
    stop = entry - stop_distance if bullish else entry + stop_distance
    stop_points = stop_distance / request.point_size
    if stop_points <= 0:
        return None
    partial = entry + stop_distance if bullish else entry - stop_distance
    target = entry + stop_distance * 2 if bullish else entry - stop_distance * 2
    return Setup(
        action,
        "momentum_atr_breakout",
        entry,
        stop,
        partial,
        target,
        stop_points,
        "not_applicable",
        ema20,
        atr14,
        ema50,
        upper_breakout if bullish else lower_breakout,
    )


def _momentum_setup_for_candle(request: DecisionRequest) -> Setup | None:
    if not request.candles:
        return None
    key = f"momentum:{request.bot_id or request.symbol}:{request.symbol}:{request.timeframe}"
    candle_timestamp = request.candles[-1].timestamp_utc
    cached = _setup_cache.get(key)
    if cached and cached[0] == candle_timestamp:
        return cached[1]
    setup = _momentum_atr_setup(request)
    _setup_cache[key] = (candle_timestamp, setup)
    return setup


def _rsi_bollinger_setup(request: DecisionRequest) -> Setup | None:
    candles = request.candles
    if len(candles) < 22:
        return None
    closes = [candle.close for candle in candles]
    current = candles[-1]
    basis_values = closes[-20:]
    basis = fmean(basis_values)
    deviation = pstdev(basis_values)
    upper_band = basis + deviation * 2
    lower_band = basis - deviation * 2
    rsi14 = _rsi(closes, 14)
    atr14 = _atr(candles, 14)
    bullish = current.low <= lower_band and current.close > lower_band and current.close > current.open and rsi14 <= 45
    bearish = current.high >= upper_band and current.close < upper_band and current.close < current.open and rsi14 >= 55
    if not bullish and not bearish:
        return None
    action = DecisionAction.BUY if bullish else DecisionAction.SELL
    entry = request.ask if bullish else request.bid
    stop = current.low - atr14 * .25 if bullish else current.high + atr14 * .25
    stop_distance = abs(entry - stop)
    if stop_distance <= 0 or (bullish and basis <= entry) or (bearish and basis >= entry):
        return None
    stop_points = stop_distance / request.point_size
    partial = basis
    target = entry + stop_distance * 2 if bullish else entry - stop_distance * 2
    return Setup(
        action=action,
        setup_type="rsi_bollinger_reversion",
        entry=entry,
        stop=stop,
        partial=partial,
        target=target,
        stop_points=stop_points,
        flow_mode="not_applicable",
        ema20=basis,
        atr14=atr14,
        rsi14=rsi14,
        bollinger_upper=upper_band,
        bollinger_lower=lower_band,
    )


def _rsi_bollinger_setup_for_candle(request: DecisionRequest) -> Setup | None:
    if not request.candles:
        return None
    key = f"rsi_bollinger:{request.bot_id or request.symbol}:{request.symbol}:{request.timeframe}"
    candle_timestamp = request.candles[-1].timestamp_utc
    cached = _setup_cache.get(key)
    if cached and cached[0] == candle_timestamp:
        return cached[1]
    setup = _rsi_bollinger_setup(request)
    _setup_cache[key] = (candle_timestamp, setup)
    return setup


def _candidate_response(
    request: DecisionRequest,
    settings: Settings,
    setup: Setup,
    checks: list[RiskCheck],
    flow: FlowAnalysis,
    *,
    executable: bool,
    reason: str,
    strategy_profile: str,
) -> DecisionResponse:
    size = round(_position_size(request.account.balance, settings.risk_per_trade_pct, setup.stop_points, request.value_per_point_per_lot), 2)
    candle_timestamp = request.candles[-1].timestamp_utc
    metadata: dict[str, str | int | float | bool] = {
        "strategy_profile": strategy_profile,
        "candidate": True,
        "candle_timestamp_utc": candle_timestamp.isoformat(),
        "setup_type": setup.setup_type,
        "flow_status": flow.status,
        "flow_ready": flow.ready,
        "flow_confirmed": flow.confirmed,
        "flow_contradicted": flow.contradicted,
        "flow_policy": settings.fimath_flow_policy,
        "ema20": round(setup.ema20, 5),
        "atr14": round(setup.atr14, 5),
        "suggested_size": size,
        "suggested_action": setup.action.value,
    }
    if flow.book_z is not None:
        metadata["book_z"] = round(flow.book_z, 5)
    if flow.tick_z is not None:
        metadata["tick_z"] = round(flow.tick_z, 5)
    if flow.score is not None:
        metadata["flow_score"] = round(flow.score, 5)
    if setup.ema50 is not None:
        metadata["ema50"] = round(setup.ema50, 5)
    if setup.breakout_level is not None:
        metadata["breakout_level"] = round(setup.breakout_level, 5)
    if setup.rsi14 is not None:
        metadata["rsi14"] = round(setup.rsi14, 5)
    if setup.bollinger_upper is not None:
        metadata["bollinger_upper"] = round(setup.bollinger_upper, 5)
    if setup.bollinger_lower is not None:
        metadata["bollinger_lower"] = round(setup.bollinger_lower, 5)
    return DecisionResponse(
        action=setup.action if executable else DecisionAction.HOLD,
        reason=reason,
        size=size if executable else 0.0,
        risk_amount=round(request.account.balance * settings.risk_per_trade_pct / 100, 2),
        entry_price=setup.entry,
        stop_loss_price=setup.stop,
        take_profit_price=setup.target,
        stop_loss_points=round(setup.stop_points, 2),
        take_profit_points=round(setup.stop_points * 2, 2),
        partial_take_profit_price=setup.partial,
        final_take_profit_price=setup.target,
        partial_close_pct=settings.fimath_partial_pct,
        move_stop_to_breakeven=True,
        risk_checks=checks,
        metadata=metadata,
    )


def _evaluate_fimath(request: DecisionRequest, settings: Settings, strategy_profile: str) -> DecisionResponse:
    flow_window = _record_flow(request, settings.fimath_flow_window_seconds)
    setup = _setup_for_candle(request)
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
    flow = _flow_analysis(
        flow_window,
        setup.action,
        settings.fimath_flow_window_seconds,
        settings.fimath_flow_min_samples,
        settings.fimath_flow_z_threshold,
    )
    policy = settings.fimath_flow_policy
    flow_eligible = flow.ready and not flow.contradicted and (policy == "veto" or flow.confirmed)
    checks.append(RiskCheck(name="flow_ready", passed=flow.ready, detail=flow.status))
    checks.append(RiskCheck(name="flow_veto", passed=not flow.contradicted, detail=flow.status))
    checks.append(RiskCheck(name="flow_policy", passed=flow_eligible, detail=f"policy={policy}"))
    if not flow.ready:
        return _candidate_response(request, settings, setup, checks, flow, executable=False, reason=flow.status, strategy_profile=strategy_profile)
    if flow.contradicted:
        return _candidate_response(request, settings, setup, checks, flow, executable=False, reason="flow_contradiction", strategy_profile=strategy_profile)
    if policy == "required" and not flow.confirmed:
        return _candidate_response(request, settings, setup, checks, flow, executable=False, reason="flow_not_confirmed", strategy_profile=strategy_profile)
    executable = settings.fimath_mode == "live" and settings.enable_live_decisions and flow_eligible
    checks.append(RiskCheck(name="fimath_live_enabled", passed=executable, detail=f"mode={settings.fimath_mode}"))
    return _candidate_response(
        request,
        settings,
        setup,
        checks,
        flow,
        executable=executable,
        reason="fimath_validated" if executable else "fimath_shadow_signal",
        strategy_profile=strategy_profile,
    )


def _evaluate_momentum_atr(request: DecisionRequest, settings: Settings, strategy_profile: str) -> DecisionResponse:
    setup = _momentum_setup_for_candle(request)
    checks = [
        RiskCheck(name="symbol_match", passed=request.symbol.upper() == settings.default_symbol.upper(), detail=f"expected={settings.default_symbol}"),
        RiskCheck(name="timeframe_match", passed=request.timeframe.upper() == settings.default_timeframe.upper(), detail=f"expected={settings.default_timeframe}"),
        RiskCheck(name="spread_limit", passed=request.spread_points <= settings.max_spread_points, detail=f"max={settings.max_spread_points}"),
        RiskCheck(name="momentum_atr_setup", passed=setup is not None, detail="ema20/ema50 + breakout_12 + atr14"),
    ]
    if not all(check.passed for check in checks[:3]):
        return DecisionResponse(action=DecisionAction.HOLD, reason="market_filter_mismatch", risk_checks=checks)
    if setup is None:
        return DecisionResponse(action=DecisionAction.HOLD, reason="momentum_atr_setup_not_confirmed", risk_checks=checks)
    flow = FlowAnalysis(True, False, False, "not_applicable")
    executable = settings.enable_live_decisions and settings.fimath_mode == "live"
    checks.append(RiskCheck(name="shadow_mode", passed=not executable, detail=f"mode={settings.fimath_mode}"))
    return _candidate_response(
        request,
        settings,
        setup,
        checks,
        flow,
        executable=executable,
        reason="momentum_atr_validated" if executable else "momentum_atr_shadow_signal",
        strategy_profile=strategy_profile,
    )


def _evaluate_rsi_bollinger(request: DecisionRequest, settings: Settings, strategy_profile: str) -> DecisionResponse:
    setup = _rsi_bollinger_setup_for_candle(request)
    checks = [
        RiskCheck(name="symbol_match", passed=request.symbol.upper() == settings.default_symbol.upper(), detail=f"expected={settings.default_symbol}"),
        RiskCheck(name="timeframe_match", passed=request.timeframe.upper() == settings.default_timeframe.upper(), detail=f"expected={settings.default_timeframe}"),
        RiskCheck(name="spread_limit", passed=request.spread_points <= settings.max_spread_points, detail=f"max={settings.max_spread_points}"),
        RiskCheck(name="rsi_bollinger_setup", passed=setup is not None, detail="bollinger_20_2 + rsi14 + rejection"),
    ]
    if not all(check.passed for check in checks[:3]):
        return DecisionResponse(action=DecisionAction.HOLD, reason="market_filter_mismatch", risk_checks=checks)
    if setup is None:
        return DecisionResponse(action=DecisionAction.HOLD, reason="rsi_bollinger_setup_not_confirmed", risk_checks=checks)
    flow = FlowAnalysis(True, False, False, "not_applicable")
    executable = settings.enable_live_decisions and settings.fimath_mode == "live"
    checks.append(RiskCheck(name="shadow_mode", passed=not executable, detail=f"mode={settings.fimath_mode}"))
    return _candidate_response(
        request,
        settings,
        setup,
        checks,
        flow,
        executable=executable,
        reason="rsi_bollinger_validated" if executable else "rsi_bollinger_shadow_signal",
        strategy_profile=strategy_profile,
    )


def evaluate_decision(request: DecisionRequest, settings: Settings, strategy_profile: str | None = None) -> DecisionResponse:
    profile = strategy_profile or settings.strategy_profile
    if profile == "momentum_atr_breakout":
        return _evaluate_momentum_atr(request, settings, profile)
    if profile == "rsi_bollinger_reversion":
        return _evaluate_rsi_bollinger(request, settings, profile)
    if profile == "fimath_ema20_flow":
        return _evaluate_fimath(request, settings, profile)
    return DecisionResponse(
        action=DecisionAction.HOLD,
        reason="unsupported_strategy_profile",
        risk_checks=[RiskCheck(name="strategy_profile", passed=False, detail=profile)],
        metadata={"strategy_profile": profile},
    )


def reset_strategy_state() -> None:
    """Clear in-memory windows and candle caches for deterministic tests."""
    _flow_windows.clear()
    _setup_cache.clear()
