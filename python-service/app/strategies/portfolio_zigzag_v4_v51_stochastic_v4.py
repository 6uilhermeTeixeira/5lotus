"""Shadow portfolio of ZigZag V4.0/V5.1 and Stochastic Sell V4."""

from __future__ import annotations

import json

PROFILE = "portfolio_zigzag_v4_v51_stochastic_v4_shadow"
MAX_SIMULTANEOUS_POSITIONS = 3


def _allocate(response, request, settings, component: str):
    from .. import strategy as engine

    risk_amount = round(request.account.balance * settings.risk_per_trade_pct / 100, 2)
    suggested_size = engine._position_size(
        request.account.balance,
        settings.risk_per_trade_pct,
        float(response.stop_loss_points or 0),
        request.value_per_point_per_lot,
    )
    response.action = engine.DecisionAction.HOLD
    response.size = 0.0
    response.risk_amount = risk_amount
    response.reason = "portfolio_zigzag_v4_v51_stochastic_v4_parallel_shadow_signal"
    response.metadata.update({
        "strategy_profile": PROFILE,
        "combined_component": component,
        "parallel_position_scope": component,
        "parallel_risk_pct": settings.risk_per_trade_pct,
        "suggested_size": round(suggested_size, 2),
        "portfolio_shared_position_limit": MAX_SIMULTANEOUS_POSITIONS,
        "experimental_shadow_lock": True,
    })
    response.risk_checks.append(engine.RiskCheck(
        name="portfolio_parallel_allocation", passed=True,
        detail=f"component={component}; max_positions={MAX_SIMULTANEOUS_POSITIONS}",
    ))
    response.risk_checks.append(engine.RiskCheck(
        name="experimental_shadow_lock", passed=True, detail="execution_permanently_disabled",
    ))
    return response


def evaluate(request, settings):
    from .. import strategy as engine
    from . import zigzag_v10, zigzag_v8

    v4 = zigzag_v10.evaluate(request, settings)
    v51 = zigzag_v8.evaluate(request, settings)
    stochastic = engine._evaluate_stochastic_sell_v4(request, settings, "stochastic_sell_v4_retest_shadow")
    v4_candidate = bool(v4.metadata.get("candidate"))
    v51_candidate = bool(v51.metadata.get("candidate"))
    stochastic_candidate = bool(stochastic.metadata.get("candidate"))

    # V4.0 and V5.1 intentionally retain separate entries, even when their
    # timestamp and side coincide.  The portfolio models this as two distinct
    # risk allocations rather than silently collapsing the duplicate.
    candidates = []
    if v4_candidate:
        candidates.append(("zigzag-v4.0", v4))
    if v51_candidate:
        candidates.append(("zigzag-v5.1", v51))
    if stochastic_candidate:
        candidates.append(("stochastic-v4", stochastic))

    existing = sum(1 for position in request.positions if position.symbol.upper() == request.symbol.upper())
    available_slots = max(0, MAX_SIMULTANEOUS_POSITIONS - existing)
    selected = candidates[:available_slots]
    parallel = [_allocate(candidate, request, settings, component) for component, candidate in selected]
    reasons = {
        "zigzag_v4": v4.reason,
        "zigzag_v51": v51.reason,
        "stochastic_v4": stochastic.reason,
    }
    return engine.DecisionResponse(
        action=engine.DecisionAction.HOLD,
        reason="portfolio_zigzag_v4_v51_stochastic_v4_parallel_candidates" if parallel else "portfolio_zigzag_v4_v51_stochastic_v4_no_candidate",
        risk_checks=[
            engine.RiskCheck(name="portfolio_zigzag_duplicate", passed=True, detail="intentional_independent_v4.0_and_v5.1_allocations"),
            engine.RiskCheck(name="portfolio_parallel_slots", passed=bool(selected) or not candidates, detail=f"available={available_slots}"),
            engine.RiskCheck(name="experimental_shadow_lock", passed=True, detail="execution_permanently_disabled"),
        ],
        metadata={
            "strategy_profile": PROFILE,
            "candidate": False,
            "parallel_execution": "v4.0_v5.1_and_stochastic_v4_can_coexist",
            "parallel_max_positions": MAX_SIMULTANEOUS_POSITIONS,
            "parallel_max_aggregate_risk_pct": settings.risk_per_trade_pct * MAX_SIMULTANEOUS_POSITIONS,
            "zigzag_duplicate_intentional": v4_candidate and v51_candidate,
            "zigzag_selected_component": None,
            "component_reasons_json": json.dumps(reasons, sort_keys=True),
            "experimental_shadow_lock": True,
            "research_status": "parallel_portfolio_requires_unified_replay_and_parallel_executor_validation",
        },
        parallel_candidates=parallel,
    )
