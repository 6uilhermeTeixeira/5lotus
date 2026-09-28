"""Candle-based Scalp-family strategy handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas import DecisionRequest, DecisionResponse


def evaluate(profile: str, request: "DecisionRequest", settings: "Settings") -> "DecisionResponse | None":
    from .. import strategy as engine

    if profile == "zigzag_scalper_v13_m30_close_shadow":
        from . import zigzag_v13

        return zigzag_v13.evaluate(request, settings)
    if profile == engine.ZIGZAG_SCALPER_V4_PROFILE:
        return engine._evaluate_zigzag_scalper_v4_day_filters(request, settings)
    handlers = {
        "happy_gold_zigzag_scalper": engine._evaluate_happy_gold_zigzag_scalper,
        "happy_gold_zigzag_regime_confirmed": engine._evaluate_happy_gold_zigzag_regime_confirmed,
    }
    handler = handlers.get(profile)
    return handler(request, settings, profile) if handler else None
