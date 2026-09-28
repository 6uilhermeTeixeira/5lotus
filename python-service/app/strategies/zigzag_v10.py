"""V6.0 contextual router: buy candidates use V5.2, sells use V5.1."""

from __future__ import annotations

PROFILE = "zigzag_scalper_v10_context_router_shadow"


def evaluate(request, settings):
    """Route a V2.1 candidate to exactly one directional contextual branch.

    The router does not create a setup or merge branch outcomes.  The V2.1
    suggested side chooses the branch before that branch's filter is evaluated.
    """
    from .. import strategy as engine
    from . import zigzag_v7

    base = engine._evaluate_zigzag_scalper_v5(request, settings)
    side = str(base.metadata.get("suggested_action", ""))
    if side == engine.DecisionAction.BUY.value:
        response = engine._evaluate_zigzag_scalper_v52(request, settings)
        branch = "v52_buy_context"
    elif side == engine.DecisionAction.SELL.value:
        response = zigzag_v7.evaluate(request, settings)
        branch = "v51_sell_context"
    else:
        response = base
        branch = "no_base_signal"

    response.action = engine.DecisionAction.HOLD
    response.size = 0.0
    response.risk_checks.append(
        engine.RiskCheck(name="v60_context_branch", passed=True, detail=branch)
    )
    response.metadata.update({
        "strategy_profile": PROFILE,
        "v60_base_strategy": engine.ZIGZAG_SCALPER_V5_PROFILE,
        "v60_selected_branch": branch,
        "v60_router_input_side": side or None,
        "v60_alternative_branch_evaluated": False,
        "experimental_shadow_lock": True,
        "research_status": "directional_context_router_requires_unified_walk_forward_and_broker_tick_forward_validation",
    })
    if response.metadata.get("candidate"):
        response.reason = "zigzag_scalper_v60_context_router_shadow_signal"
    return response
