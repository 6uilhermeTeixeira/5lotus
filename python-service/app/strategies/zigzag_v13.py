"""V1.3: ZigZag M30 with a confirmed candle-close trigger.

This variant deliberately uses OHLC only.  It keeps the V1 pivot geometry and
exit model, but replaces the quote breakout with a completed-M30 close beyond
the last confirmed fractal and an entry window on the first following M5.
"""

from datetime import time, timedelta, timezone


PROFILE = "zigzag_scalper_v13_m30_close_shadow"


def evaluate(request, settings):
    from .. import strategy as engine

    session_time = request.timestamp_utc.astimezone(timezone.utc).time()
    in_research_session = time(3, 0) <= session_time < time(19, 0)
    same_symbol_positions = [
        position for position in request.positions
        if position.symbol.upper() == request.symbol.upper()
    ]
    m30 = engine._aggregate_completed_candles(request.candles, 30, request.timestamp_utc)

    setup = None
    trigger_window = False
    close_confirmation = False
    pivot_high = pivot_low = None
    if len(m30) >= 7:
        signal_candle = m30[-1]
        signal_end = signal_candle.timestamp_utc + timedelta(minutes=30)
        now = request.timestamp_utc.astimezone(timezone.utc)
        trigger_window = signal_end <= now < signal_end + timedelta(minutes=5)
        # Exclude the signal candle from pivot discovery: it cannot confirm a
        # fractal that is still being used as the breakout trigger.
        pivot_high, pivot_low = engine._latest_confirmed_zigzag_levels(m30[:-1])
        previous_close = m30[-2].close
        buy = bool(pivot_high is not None and previous_close <= pivot_high < signal_candle.close)
        sell = bool(pivot_low is not None and previous_close >= pivot_low > signal_candle.close)
        close_confirmation = buy or sell
        if trigger_window and close_confirmation:
            if buy and sell:
                buy = signal_candle.close - float(pivot_high) >= float(pivot_low) - signal_candle.close
                sell = not buy
            action = engine.DecisionAction.BUY if buy else engine.DecisionAction.SELL
            entry = request.ask if buy else request.bid
            stop_points = 240.0
            target_points = 1000.0
            stop = entry - stop_points * request.point_size if buy else entry + stop_points * request.point_size
            target = entry + target_points * request.point_size if buy else entry - target_points * request.point_size
            setup = engine.Setup(
                action=action,
                setup_type="zigzag_v13_m30_close_confirmation",
                entry=entry,
                stop=stop,
                partial=target,
                target=target,
                stop_points=stop_points,
                flow_mode="not_applicable",
                ema20=signal_candle.close,
                atr14=engine._atr(m30, min(14, len(m30))),
                breakout_level=float(pivot_high if buy else pivot_low),
                partial_close_pct=100.0,
                move_stop_to_breakeven=False,
                max_holding_bars=2,
            )

    checks = [
        engine.RiskCheck(name="symbol_match", passed=request.symbol.upper() == "XAUUSD", detail="expected=XAUUSD"),
        engine.RiskCheck(name="timeframe_match", passed=request.timeframe.upper() == "M5", detail="expected=M5; signal=M30"),
        engine.RiskCheck(name="spread_limit", passed=request.spread_points <= settings.max_spread_points, detail=f"max={settings.max_spread_points}"),
        engine.RiskCheck(name="research_session", passed=in_research_session, detail="03:00-19:00_UTC_proxy"),
        engine.RiskCheck(name="single_position", passed=not same_symbol_positions, detail="max_positions_for_symbol=1"),
        engine.RiskCheck(name="m30_close_confirmation", passed=close_confirmation, detail="completed_M30_close_beyond_confirmed_fractal"),
        engine.RiskCheck(name="first_m5_after_m30_close", passed=trigger_window, detail="entry_window=0_to_5_minutes"),
    ]
    metadata = {
        "strategy_profile": PROFILE,
        "candidate": False,
        "signal_timeframe": "M30",
        "execution_timeframe": "M5",
        "v13_trigger": "completed_m30_close_beyond_confirmed_fractal",
        "v13_entry_window": "first_m5_after_m30_close",
        "v13_uses_ticks": False,
        "fixed_stop_points": 240,
        "fixed_target_points": 1000,
        "max_holding_bars": 2,
        "experimental_shadow_lock": True,
        "research_status": "new_geometry_requires_ohlc_replay_and_forward_validation",
    }
    if setup is None or not all(check.passed for check in checks[:5]):
        return engine.DecisionResponse(
            action=engine.DecisionAction.HOLD,
            reason="zigzag_scalper_v13_trigger_not_confirmed",
            risk_checks=checks,
            metadata=metadata,
        )
    response = engine._candidate_response(
        request, settings, setup, checks, engine.FlowAnalysis(True, False, False, "not_applicable"),
        executable=False, reason="zigzag_scalper_v13_m30_close_shadow_signal", strategy_profile=PROFILE,
    )
    response.risk_amount = round(setup.stop_points * request.value_per_point_per_lot * .10, 2)
    response.metadata.update(metadata | {"candidate": True, "suggested_size": .10})
    response.risk_checks.append(engine.RiskCheck(name="experimental_shadow_lock", passed=True, detail="execution_permanently_disabled"))
    return response
