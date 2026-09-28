from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas import DecisionRequest, DecisionResponse


def evaluate(profile: str, request: "DecisionRequest", settings: "Settings") -> "DecisionResponse | None":
    from .. import strategy as engine
    from . import portfolio_zigzag_v4_v51_stochastic_v4

    if profile in engine.WEIGHTED_PORTFOLIO_PROFILES:
        return engine._evaluate_weighted_portfolio_6_7(request, settings, profile)
    if profile == engine.HAPPY_GOLD_COMBINED_PROFILE:
        return engine._evaluate_happy_gold_combined_portfolio(request, settings)
    if profile == engine.ADAPTIVE_V3_COMBINED_PROFILE:
        return engine._evaluate_adaptive_v3_combined_portfolio(request, settings)
    if profile == portfolio_zigzag_v4_v51_stochastic_v4.PROFILE:
        return portfolio_zigzag_v4_v51_stochastic_v4.evaluate(request, settings)
    return None
