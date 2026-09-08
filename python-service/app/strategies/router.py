from __future__ import annotations

from ..config import Settings
from ..schemas import DecisionRequest, DecisionResponse

from . import core, portfolio, tick


def evaluate_profile(profile: str, request: DecisionRequest, settings: Settings) -> DecisionResponse | None:
    for family in (core, tick, portfolio):
        if response := family.evaluate(profile, request, settings):
            return response
    return None
