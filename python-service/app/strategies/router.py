from __future__ import annotations

from ..config import Settings
from ..schemas import DecisionRequest, DecisionResponse

from . import core, portfolio, tick
from .registry import strategy_definition


def evaluate_profile(profile: str, request: DecisionRequest, settings: Settings) -> DecisionResponse | None:
    definition = strategy_definition(profile)
    if definition is not None:
        family = {"core": core, "tick": tick, "portfolio": portfolio}[definition.route]
        return family.evaluate(profile, request, settings)
    # Research-only and legacy profiles remain routable while they are migrated
    # into the registry; active catalog profiles must always be registered.
    for family in (core, tick, portfolio):
        if response := family.evaluate(profile, request, settings):
            return response
    return None
