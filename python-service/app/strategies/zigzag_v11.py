"""V7.0 final orchestration over the contextual V4.0 candidate."""

from __future__ import annotations

PROFILE = "zigzag_scalper_v11_final_orchestrator_shadow"


def _week_of_month(timestamp) -> int:
    return min(5, (timestamp.day - 1) // 7 + 1)


def _accuracy_cycle_allows(timestamp, side: str) -> bool:
    week = _week_of_month(timestamp)
    weekday = timestamp.weekday()
    return ((weekday == 0 and week == 2) or (weekday == 1 and week == 3 and side == "buy") or (weekday == 4 and week == 4))


def evaluate(request, settings):
    from .. import strategy as engine
    from . import zigzag_v10

    response = zigzag_v10.evaluate(request, settings)
    side = str(response.metadata.get("suggested_action", ""))
    timestamp = request.timestamp_utc.astimezone(engine.timezone.utc)
    day_allowed, day_rule = engine._zigzag_v4_calendar_allows(timestamp, side or None)
    cycle_allowed = _accuracy_cycle_allows(timestamp, side)
    candidate = bool(response.metadata.get("candidate"))
    temporal_ok = candidate and day_allowed and cycle_allowed
    response.risk_checks.extend([
        engine.RiskCheck(name="v70_day_hour_direction_filter", passed=day_allowed, detail=f"rule={day_rule}"),
        engine.RiskCheck(name="v70_accuracy_cycle_filter", passed=cycle_allowed, detail="week_of_month_calendar"),
        engine.RiskCheck(name="v70_temporal_selector", passed=True, detail="contextual_candidate_preserved"),
    ])
    if candidate and not temporal_ok:
        response.metadata["candidate"] = False
        response.reason = "zigzag_scalper_v11_temporal_orchestration_block"
    elif candidate:
        response.reason = "zigzag_scalper_v11_final_orchestration_shadow_signal"
    response.action = engine.DecisionAction.HOLD
    response.size = 0.0
    response.metadata.update({
        "strategy_profile": PROFILE,
        "v70_base_strategy": engine.ZIGZAG_SCALPER_V10_PROFILE,
        "v70_temporal_filters": ["v5_day_hour_direction", "v5_accuracy_cycle"],
        "v70_temporal_filter_passed": temporal_ok,
        "v70_day_rule": day_rule,
        "v70_week_of_month": _week_of_month(timestamp),
        "v70_temporal_route": "contextual_v4_preserved",
        "v70_alternative_trigger_evaluated": False,
        "experimental_shadow_lock": True,
        "research_status": "final_orchestration_requires_unified_causal_replay_and_forward_validation",
    })
    return response
