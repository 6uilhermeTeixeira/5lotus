from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas import DecisionRequest, DecisionResponse


def evaluate(profile: str, request: "DecisionRequest", settings: "Settings") -> "DecisionResponse | None":
    from .. import strategy as engine

    handlers = {
        "stochastic_sell_session": engine._evaluate_stochastic_sell_session,
        "stochastic_sell_v2_shadow": engine._evaluate_stochastic_sell_v2,
        "stochastic_sell_v3_adaptive_shadow": engine._evaluate_stochastic_sell_v3,
        "multitimeframe_trend_pullback": engine._evaluate_multitimeframe_trend_pullback,
        "multitimeframe_trend_pullback_v2_shadow": engine._evaluate_multitimeframe_trend_pullback,
        "multitimeframe_trend_pullback_v3_adaptive_shadow": engine._evaluate_multitimeframe_trend_pullback,
        "happy_gold_zigzag_scalper": engine._evaluate_happy_gold_zigzag_scalper,
        "happy_gold_zigzag_regime_confirmed": engine._evaluate_happy_gold_zigzag_regime_confirmed,
    }
    handler = handlers.get(profile)
    return handler(request, settings, profile) if handler else None
