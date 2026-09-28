"""V8 accuracy cycle: a conservative calendar gate over the V7.2 signal."""
from . import zigzag_v72

PROFILE = "zigzag_scalper_v8_accuracy_cycle_shadow"


def week_of_month(timestamp):
    return min(5, (timestamp.day - 1) // 7 + 1)


def calendar_allows(timestamp, side):
    weekday = timestamp.weekday()
    week = week_of_month(timestamp)
    return (
        (weekday == 0 and week == 2)  # Monday, second week
        or (weekday == 1 and week == 3 and side == "buy")  # Tuesday, third week
        or (weekday == 4 and week == 4)  # Friday, fourth week
    )


def evaluate(request, settings):
    from .. import strategy as engine

    response = zigzag_v72.evaluate(request, settings)
    side = str(response.metadata.get("suggested_action", ""))
    calendar_ok = calendar_allows(request.timestamp_utc, side)
    response.risk_checks.append(engine.RiskCheck(name="v8_accuracy_cycle", passed=calendar_ok, detail="week_of_month_calendar"))
    if response.metadata.get("candidate"):
        response.metadata["candidate"] = bool(calendar_ok)
        response.reason = "v8_accuracy_cycle_shadow_signal" if calendar_ok else "v8_calendar_block"
    response.metadata.update({
        "strategy_profile": PROFILE,
        "v8_week_of_month": week_of_month(request.timestamp_utc),
        "v8_calendar_allows": calendar_ok,
        "experimental_shadow_lock": True,
        "research_status": "provisional_calendar_requires_forward_validation",
    })
    return response
