from __future__ import annotations

from typing import TYPE_CHECKING

from . import buy, scalp, sell
from .registry import strategy_definition

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas import DecisionRequest, DecisionResponse


def evaluate(profile: str, request: "DecisionRequest", settings: "Settings") -> "DecisionResponse | None":
    definition = strategy_definition(profile)
    family = definition.family if definition is not None else None
    if family == "sell":
        return sell.evaluate(profile, request, settings)
    if family == "buy":
        return buy.evaluate(profile, request, settings)
    if family == "scalp":
        return scalp.evaluate(profile, request, settings)
    for handler_group in (sell, buy, scalp):
        if response := handler_group.evaluate(profile, request, settings):
            return response
    return None
