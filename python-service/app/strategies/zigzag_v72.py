"""V7.2 hybrid: V3 on Wednesday/Thursday, V7 on the remaining UTC days."""
from . import zigzag_v7

PROFILE = "zigzag_scalper_v72_v3_wed_thu_shadow"
V3_RELEASE_WEEKDAYS = {2, 3}  # Wednesday, Thursday; datetime.weekday() in UTC.


def evaluate(request, settings):
    """Keep both branches shadow-only, regardless of V3 demo settings."""
    from .. import strategy as engine

    weekday = request.timestamp_utc.weekday()
    if weekday in V3_RELEASE_WEEKDAYS:
        response = engine._evaluate_zigzag_scalper_v3(request, settings)
        branch = "v3_pure_wed_thu"
    else:
        response = zigzag_v7.evaluate(request, settings)
        branch = "v7_directional_other_days"

    response.action = engine.DecisionAction.HOLD
    response.size = 0.0
    response.risk_checks = [check for check in response.risk_checks if check.name != "demo_execution_gate"]
    response.risk_checks.append(engine.RiskCheck(name="experimental_shadow_lock", passed=True, detail="v72_research_only"))
    response.metadata.update({
        "strategy_profile": PROFILE,
        "v72_branch": branch,
        "v72_v3_release_day": weekday in V3_RELEASE_WEEKDAYS,
        "experimental_shadow_lock": True,
        "research_status": "provisional_composite_requires_unified_tick_replay",
    })
    if response.metadata.get("candidate"):
        response.reason = "v72_v3_release_shadow_signal" if weekday in V3_RELEASE_WEEKDAYS else "v72_v7_shadow_signal"
    return response
