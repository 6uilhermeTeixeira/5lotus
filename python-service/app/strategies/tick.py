from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas import DecisionRequest, DecisionResponse


def evaluate(profile: str, request: "DecisionRequest", settings: "Settings") -> "DecisionResponse | None":
    from .. import strategy as engine

    if profile == engine.HAPPY_GOLD_TICK_IMPULSE_PROFILE:
        return engine._evaluate_happy_gold_tick_impulse(request, settings)
    if profile == engine.HAPPY_GOLD_ZIGZAG_TICK_CONTEXT_PROFILE:
        return engine._evaluate_happy_gold_zigzag_tick_context(request, settings)
    if profile == engine.HAPPY_GOLD_ZIGZAG_STRUCTURAL_TICK_PROFILE:
        return engine._evaluate_happy_gold_zigzag_structural_tick(request, settings)
    if profile == engine.HAPPY_GOLD_ZIGZAG_NORMALIZED_RANGE_PROFILE:
        return engine._evaluate_happy_gold_zigzag_structural_tick(
            request, settings, strategy_profile=profile,
            normalized_range_max=float(getattr(settings, "happy_gold_normalized_range_max", 1.876955192)),
        )
    if profile == engine.ZIGZAG_SCALPER_V2_PROFILE:
        return engine._evaluate_happy_gold_zigzag_structural_tick(
            request, settings, strategy_profile=profile, fixed_lot=.40,
        )
    if profile == engine.ZIGZAG_SCALPER_V3_PROFILE:
        return engine._evaluate_zigzag_scalper_v3(request, settings)
    if profile == engine.ZIGZAG_SCALPER_V4_PROFILE:
        return engine._evaluate_zigzag_scalper_v4(request, settings)
    if profile == engine.HAPPY_GOLD_MULTIWINDOW_TICK_SCORE_PROFILE:
        return engine._evaluate_happy_gold_multiwindow_tick_score(request, settings)
    return None
