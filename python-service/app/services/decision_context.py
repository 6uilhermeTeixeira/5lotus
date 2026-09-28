"""Small, deterministic policies used by the decision application flow."""

from copy import copy
from typing import Any

from ..config import Settings
from ..schemas import DecisionAction, DecisionRequest, DecisionResponse


def prepare_strategy_settings(
    base_settings: Settings,
    payload: DecisionRequest,
    strategy_profile: str,
    *,
    portfolio_risk_state: dict[str, Any] | None = None,
) -> Settings:
    """Scope symbol/timeframe and optional portfolio state to one decision."""
    if not payload.bot_id:
        return base_settings
    scoped = copy(base_settings)
    scoped.default_symbol = payload.symbol
    scoped.default_timeframe = payload.timeframe
    if portfolio_risk_state is not None:
        scoped.portfolio_risk_state = portfolio_risk_state
    return scoped


def enforce_shadow_minimum(
    response: DecisionResponse,
    *,
    validation_variant: str,
    closed_paper_trades: int,
    minimum_closed_trades: int,
) -> DecisionResponse:
    """Block live-direction output until the configured shadow sample exists."""
    response.metadata["validation_variant"] = validation_variant
    response.metadata["closed_paper_trades"] = closed_paper_trades
    if response.action.value in {"buy", "sell"} and closed_paper_trades < minimum_closed_trades:
        response.action = DecisionAction.HOLD
        response.reason = "shadow_minimum_not_reached"
        response.size = 0.0
    return response
