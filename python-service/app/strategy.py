from dataclasses import dataclass

from .config import Settings
from .schemas import CandleSnapshot, DecisionAction, DecisionRequest, DecisionResponse, RiskCheck


@dataclass
class SetupEvaluation:
    action: DecisionAction
    breakout_level: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_points: float
    take_profit_points: float
    rr_ratio: float
    breakout_confirmed: bool
    pullback_confirmed: bool
    ignition_confirmed: bool
    stop_reference: str


def compute_position_size(balance: float, risk_pct: float, stop_loss_points: float, value_per_point_per_lot: float) -> float:
    risk_amount = balance * (risk_pct / 100.0)
    return risk_amount / (stop_loss_points * value_per_point_per_lot)


def average_body(candles: list[CandleSnapshot], end_idx: int, period: int) -> float:
    window = candles[end_idx - period : end_idx]
    return sum(abs(c.close - c.open) for c in window) / period


def average_volume(candles: list[CandleSnapshot], end_idx: int, period: int) -> float:
    window = candles[end_idx - period : end_idx]
    return sum(c.volume for c in window) / period


def compute_atr(candles: list[CandleSnapshot], end_idx: int, period: int) -> float:
    window = candles[end_idx - period + 1 : end_idx + 1]
    true_ranges: list[float] = []

    for idx, candle in enumerate(window):
        previous_close = window[idx - 1].close if idx > 0 else candles[end_idx - period].close
        true_ranges.append(max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))

    return sum(true_ranges) / period


def is_fractal_low(candles: list[CandleSnapshot], idx: int) -> bool:
    center = candles[idx]
    return (
        center.low < candles[idx - 1].low
        and center.low < candles[idx - 2].low
        and center.low < candles[idx + 1].low
        and center.low < candles[idx + 2].low
    )


def is_fractal_high(candles: list[CandleSnapshot], idx: int) -> bool:
    center = candles[idx]
    return (
        center.high > candles[idx - 1].high
        and center.high > candles[idx - 2].high
        and center.high > candles[idx + 1].high
        and center.high > candles[idx + 2].high
    )


def find_last_fractal(candles: list[CandleSnapshot], action: DecisionAction) -> CandleSnapshot | None:
    for idx in range(len(candles) - 3, 1, -1):
        if action == DecisionAction.BUY and is_fractal_low(candles, idx):
            return candles[idx]
        if action == DecisionAction.SELL and is_fractal_high(candles, idx):
            return candles[idx]
    return None


def evaluate_setup(request: DecisionRequest, settings: Settings) -> SetupEvaluation | None:
    candles = request.candles
    breakout_idx = len(candles) - 3
    pullback_idx = len(candles) - 2
    ignition_idx = len(candles) - 1

    breakout = candles[breakout_idx]
    pullback = candles[pullback_idx]
    ignition = candles[ignition_idx]

    highest_20 = max(c.high for c in candles[breakout_idx - 20 : breakout_idx])
    lowest_20 = min(c.low for c in candles[breakout_idx - 20 : breakout_idx])
    avg_body_10 = average_body(candles, breakout_idx, 10)
    avg_volume_10 = average_volume(candles, pullback_idx, 10)
    avg_volume_20 = average_volume(candles, ignition_idx, 20)

    bullish_breakout = breakout.close > highest_20 and abs(breakout.close - breakout.open) > avg_body_10
    bearish_breakout = breakout.close < lowest_20 and abs(breakout.close - breakout.open) > avg_body_10

    if not bullish_breakout and not bearish_breakout:
        return None

    action = DecisionAction.BUY if bullish_breakout else DecisionAction.SELL
    breakout_level = highest_20 if bullish_breakout else lowest_20
    tolerance = breakout_level * 0.0005

    pullback_confirmed = (
        pullback.low <= breakout_level + tolerance
        and pullback.high >= breakout_level - tolerance
        and pullback.volume <= avg_volume_10
    )

    ignition_confirmed = False
    if action == DecisionAction.BUY:
        ignition_confirmed = ignition.close > ignition.open and ignition.close > pullback.high and ignition.volume > avg_volume_20
    else:
        ignition_confirmed = ignition.close < ignition.open and ignition.close < pullback.low and ignition.volume > avg_volume_20

    if not pullback_confirmed or not ignition_confirmed:
        return SetupEvaluation(
            action=action,
            breakout_level=breakout_level,
            entry_price=request.ask if action == DecisionAction.BUY else request.bid,
            stop_loss_price=0.0,
            take_profit_price=0.0,
            stop_loss_points=0.0,
            take_profit_points=0.0,
            rr_ratio=0.0,
            breakout_confirmed=True,
            pullback_confirmed=pullback_confirmed,
            ignition_confirmed=ignition_confirmed,
            stop_reference="pending",
        )

    fractal = find_last_fractal(candles[:-1], action)
    if fractal is None:
        return None

    atr = compute_atr(candles, ignition_idx, 14)
    entry_price = request.ask if action == DecisionAction.BUY else request.bid
    stop_loss_price = fractal.low - atr if action == DecisionAction.BUY else fractal.high + atr
    stop_loss_points = abs(entry_price - stop_loss_price) / request.point_size
    take_profit_points = stop_loss_points * settings.min_risk_reward
    take_profit_price = (
        entry_price + (take_profit_points * request.point_size)
        if action == DecisionAction.BUY
        else entry_price - (take_profit_points * request.point_size)
    )

    return SetupEvaluation(
        action=action,
        breakout_level=breakout_level,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        stop_loss_points=stop_loss_points,
        take_profit_points=take_profit_points,
        rr_ratio=settings.min_risk_reward,
        breakout_confirmed=True,
        pullback_confirmed=True,
        ignition_confirmed=True,
        stop_reference="fractal_5_plus_atr14",
    )


def evaluate_decision(request: DecisionRequest, settings: Settings) -> DecisionResponse:
    risk_amount = round(request.account.balance * (settings.risk_per_trade_pct / 100.0), 2)
    has_minimum_history = len(request.candles) >= 23

    setup = evaluate_setup(request, settings) if has_minimum_history else None
    has_entry_signal = setup is not None and setup.action in (DecisionAction.BUY, DecisionAction.SELL)

    checks = [
        RiskCheck(
            name="symbol_match",
            passed=request.symbol.upper() == settings.default_symbol.upper(),
            detail=f"symbol={request.symbol} expected={settings.default_symbol}",
        ),
        RiskCheck(
            name="timeframe_match",
            passed=request.timeframe.upper() == settings.default_timeframe.upper(),
            detail=f"timeframe={request.timeframe} expected={settings.default_timeframe}",
        ),
        RiskCheck(
            name="spread_limit",
            passed=request.spread_points <= settings.max_spread_points,
            detail=f"spread={request.spread_points} max={settings.max_spread_points}",
        ),
        RiskCheck(
            name="history_depth",
            passed=has_minimum_history,
            detail=f"candles={len(request.candles)} min=23",
        ),
        RiskCheck(
            name="breakout_confirmed",
            passed=bool(setup and setup.breakout_confirmed),
            detail=f"breakout_confirmed={bool(setup and setup.breakout_confirmed)}",
        ),
        RiskCheck(
            name="pullback_confirmed",
            passed=bool(setup and setup.pullback_confirmed),
            detail=f"pullback_confirmed={bool(setup and setup.pullback_confirmed)}",
        ),
        RiskCheck(
            name="ignition_candle_confirmed",
            passed=bool(setup and setup.ignition_confirmed),
            detail=f"ignition_candle_confirmed={bool(setup and setup.ignition_confirmed)}",
        ),
        RiskCheck(
            name="risk_per_trade_limit",
            passed=settings.risk_per_trade_pct > 0.0,
            detail=f"risk_pct={settings.risk_per_trade_pct}",
        ),
        RiskCheck(
            name="risk_reward_minimum",
            passed=bool(setup and setup.rr_ratio >= settings.min_risk_reward),
            detail=f"rr_ratio={(setup.rr_ratio if setup else 0.0):.2f} min={settings.min_risk_reward}",
        ),
        RiskCheck(
            name="live_decisions_enabled",
            passed=(not has_entry_signal) or settings.enable_live_decisions,
            detail="live decisions stay disabled by default even for demo until the setup is validated",
        ),
    ]

    if not checks[0].passed or not checks[1].passed:
        return DecisionResponse(
            action=DecisionAction.HOLD,
            reason="market_filter_mismatch",
            risk_amount=risk_amount,
            risk_checks=checks,
            metadata={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "strategy_profile": settings.strategy_profile,
                "expected_symbol": settings.default_symbol,
                "expected_timeframe": settings.default_timeframe,
            },
        )

    if not checks[2].passed:
        return DecisionResponse(
            action=DecisionAction.HOLD,
            reason="spread_above_limit",
            risk_amount=risk_amount,
            risk_checks=checks,
            metadata={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "strategy_profile": settings.strategy_profile,
            },
        )

    if not checks[3].passed:
        return DecisionResponse(
            action=DecisionAction.HOLD,
            reason="insufficient_history",
            risk_amount=risk_amount,
            risk_checks=checks,
            metadata={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "strategy_profile": settings.strategy_profile,
            },
        )

    if not has_entry_signal:
        return DecisionResponse(
            action=DecisionAction.HOLD,
            reason="setup_not_confirmed",
            risk_amount=risk_amount,
            risk_checks=checks,
            metadata={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "strategy_profile": settings.strategy_profile,
                "risk_per_trade_pct": settings.risk_per_trade_pct,
                "min_risk_reward": settings.min_risk_reward,
            },
        )

    suggested_size = round(
        compute_position_size(
            balance=request.account.balance,
            risk_pct=settings.risk_per_trade_pct,
            stop_loss_points=setup.stop_loss_points,
            value_per_point_per_lot=request.value_per_point_per_lot,
        ),
        2,
    )

    if not checks[9].passed:
        return DecisionResponse(
            action=DecisionAction.HOLD,
            reason="live_decisions_disabled",
            size=0.0,
            risk_amount=risk_amount,
            entry_price=setup.entry_price,
            stop_loss_price=setup.stop_loss_price,
            take_profit_price=setup.take_profit_price,
            stop_loss_points=round(setup.stop_loss_points, 2),
            take_profit_points=round(setup.take_profit_points, 2),
            risk_checks=checks,
            metadata={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "strategy_profile": settings.strategy_profile,
                "suggested_action": setup.action.value,
                "suggested_size": suggested_size,
                "risk_per_trade_pct": settings.risk_per_trade_pct,
                "rr_ratio": round(setup.rr_ratio, 2),
                "min_risk_reward": settings.min_risk_reward,
                "stop_reference": setup.stop_reference,
            },
        )

    return DecisionResponse(
        action=setup.action,
        reason=f"{settings.strategy_profile}_validated",
        size=suggested_size,
        risk_amount=risk_amount,
        entry_price=setup.entry_price,
        stop_loss_price=setup.stop_loss_price,
        take_profit_price=setup.take_profit_price,
        stop_loss_points=round(setup.stop_loss_points, 2),
        take_profit_points=round(setup.take_profit_points, 2),
        risk_checks=checks,
        metadata={
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "strategy_profile": settings.strategy_profile,
            "risk_per_trade_pct": settings.risk_per_trade_pct,
            "rr_ratio": round(setup.rr_ratio, 2),
            "min_risk_reward": settings.min_risk_reward,
            "stop_reference": setup.stop_reference,
        },
    )
