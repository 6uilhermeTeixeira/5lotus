"""V1.2: original ZigZag geometry with a causal tick micro-retest trigger."""

PROFILE = "zigzag_scalper_v12_micro_retest_shadow"


def evaluate(request, settings):
    """Keep V1's setup and exits; accept only an externally reconstructed retest.

    The request indicators are deliberately explicit.  Until the tick replay and
    forward collector publish these fields, missing data fails closed instead of
    silently treating V1's breakout as a V1.2 signal.
    """
    from .. import strategy as engine

    base = engine._evaluate_happy_gold_zigzag_scalper(request, settings, PROFILE)
    checks = list(base.risk_checks)
    indicators = request.indicators
    retest_ready = indicators.get("zigzag_v12_retest_ready") == 1
    rejection = indicators.get("zigzag_v12_retest_rejection") == 1
    age_seconds = float(indicators.get("zigzag_v12_retest_age_seconds", -1))
    depth_pips = float(indicators.get("zigzag_v12_retest_depth_pips", -1))
    rejection_pips = float(indicators.get("zigzag_v12_rejection_move_pips", 0))
    max_age = float(getattr(settings, "zigzag_scalper_v12_retest_max_age_seconds", 90))
    max_depth = float(getattr(settings, "zigzag_scalper_v12_retest_max_depth_pips", 50))
    min_rejection = float(getattr(settings, "zigzag_scalper_v12_min_rejection_move_pips", 5))

    checks.extend([
        engine.RiskCheck(name="v12_retest_window_ready", passed=retest_ready, detail="causal_tick_retest_fields_present"),
        engine.RiskCheck(name="v12_retest_rejection", passed=rejection, detail="rejection_in_breakout_direction"),
        engine.RiskCheck(name="v12_retest_age", passed=0 <= age_seconds <= max_age, detail=f"max_seconds={max_age}"),
        engine.RiskCheck(name="v12_retest_depth", passed=0 <= depth_pips <= max_depth, detail=f"max_pips={max_depth}"),
        engine.RiskCheck(name="v12_rejection_move", passed=rejection_pips >= min_rejection, detail=f"min_pips={min_rejection}"),
    ])

    base.metadata.update({
        "strategy_profile": PROFILE,
        "v12_trigger": "breakout_then_causal_micro_retest_rejection",
        "v12_retest_ready": retest_ready,
        "v12_retest_rejection": rejection,
        "v12_retest_age_seconds": age_seconds,
        "v12_retest_depth_pips": depth_pips,
        "v12_rejection_move_pips": rejection_pips,
        "v12_retest_max_age_seconds": max_age,
        "v12_retest_max_depth_pips": max_depth,
        "v12_min_rejection_move_pips": min_rejection,
        "experimental_shadow_lock": True,
        "research_status": "new_geometry_requires_tick_replay_and_forward_validation",
    })

    if not all(check.passed for check in checks):
        base.action = engine.DecisionAction.HOLD
        base.size = 0.0
        base.metadata["candidate"] = False
        base.reason = "zigzag_scalper_v12_micro_retest_filter_block"
        return base

    base.action = engine.DecisionAction.HOLD
    base.size = 0.0
    base.reason = "zigzag_scalper_v12_micro_retest_shadow_signal"
    base.risk_checks.append(engine.RiskCheck(
        name="experimental_shadow_lock", passed=True, detail="execution_permanently_disabled"
    ))
    return base
