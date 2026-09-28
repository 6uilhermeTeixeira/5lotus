"""Buy-family strategy handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas import DecisionRequest, DecisionResponse


def evaluate(profile: str, request: "DecisionRequest", settings: "Settings") -> "DecisionResponse | None":
    from .. import strategy as engine

    handlers = {
        "multitimeframe_trend_pullback": engine._evaluate_multitimeframe_trend_pullback,
        "multitimeframe_trend_pullback_v2_shadow": engine._evaluate_multitimeframe_trend_pullback,
        "multitimeframe_trend_pullback_v3_adaptive_shadow": engine._evaluate_multitimeframe_trend_pullback,
        "buy_trend_pullback_breakout_v1_shadow": engine._evaluate_buy_trend_pullback_breakout_v1,
        "buy_trend_dip_stochastic_v1_shadow": engine._evaluate_buy_trend_dip_stochastic_v1,
    }
    handler = handlers.get(profile)
    return handler(request, settings, profile) if handler else None
