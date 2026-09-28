"""Sell-family strategy handlers."""

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
        "stochastic_sell_v4_retest_shadow": engine._evaluate_stochastic_sell_v4,
        "breakout_short_v1_shadow": engine._evaluate_breakout_short_v1,
        "mean_reversion_sell_v1_shadow": engine._evaluate_mean_reversion_sell_v1,
    }
    handler = handlers.get(profile)
    return handler(request, settings, profile) if handler else None
