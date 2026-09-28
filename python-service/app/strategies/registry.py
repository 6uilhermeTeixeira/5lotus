"""Declarative metadata shared by strategy routing, replay and presentation.

Keep executable rules in their family modules.  This registry owns the stable
facts that otherwise tend to be repeated across the application whenever a
strategy is added.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Protocol


StrategyFamily = Literal["scalp", "sell", "buy", "combined"]
StrategyRoute = Literal["core", "tick", "portfolio"]
RegimePolicy = Literal["external", "internal_ema50", "internal_multitimeframe", "internal_m30", "internal_portfolio"]
RegimeChannel = Literal["happy_gold", "stochastic", "multitimeframe", "portfolio"]
ReplaySession = Literal["default", "happy_gold", "combined", "impulse"]


class CatalogStrategy(Protocol):
    id: str
    strategy_profile: str
    active: bool


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    bot_id: str
    profile: str
    family: StrategyFamily
    route: StrategyRoute
    order: int
    history_bars: int = 60
    regime_policy: RegimePolicy = "external"
    operational: bool = False
    replay_supported: bool = True
    decision_history_bars: int | None = None
    regime_channels: tuple[RegimeChannel, ...] = ()
    replay_session: ReplaySession = "default"


STRATEGY_DEFINITIONS = (
    StrategyDefinition("core-zigzag", "happy_gold_zigzag_scalper", "scalp", "core", 0, regime_policy="internal_m30", decision_history_bars=1000, replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v12", "zigzag_scalper_v12_micro_retest_shadow", "scalp", "tick", 1, regime_policy="internal_m30", replay_supported=False, replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v13", "zigzag_scalper_v13_m30_close_shadow", "scalp", "core", 2, regime_policy="internal_m30", replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v2", "zigzag_scalper_v2_shadow", "scalp", "tick", 3, regime_policy="internal_m30", replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v3", "zigzag_scalper_v3_adaptive_shadow", "scalp", "tick", 4, 61, "internal_m30", True, replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v5", "zigzag_scalper_v5_adaptive_gate_shadow", "scalp", "tick", 5, 61, "internal_m30", replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v6", "zigzag_scalper_v6_stochastic_sell_gate_shadow", "scalp", "tick", 6, 4000, "internal_m30", regime_channels=("stochastic",), replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v7", "zigzag_scalper_v7_directional_shadow", "scalp", "tick", 7, replay_supported=False),
    StrategyDefinition("core-zigzag-v9", "zigzag_scalper_v9_buy_context_shadow", "scalp", "tick", 8, 4000, "internal_m30", decision_history_bars=4000, replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v10", "zigzag_scalper_v10_context_router_shadow", "scalp", "tick", 9, 4000, "internal_m30", decision_history_bars=4000, replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v4", "zigzag_scalper_v4_day_filters_shadow", "scalp", "core", 10, regime_policy="internal_m30", replay_session="happy_gold"),
    StrategyDefinition("core-zigzag-v8", "zigzag_scalper_v8_accuracy_cycle_shadow", "scalp", "tick", 11, replay_supported=False),
    StrategyDefinition("core-zigzag-v72", "zigzag_scalper_v72_v3_wed_thu_shadow", "scalp", "tick", 12, replay_supported=False),
    StrategyDefinition("core-zigzag-v11", "zigzag_scalper_v11_final_orchestrator_shadow", "scalp", "tick", 13, 4000, "internal_m30", decision_history_bars=4000, replay_session="happy_gold"),
    StrategyDefinition("core-stochastic", "stochastic_sell_session", "sell", "core", 0),
    StrategyDefinition("core-stochastic-v2", "stochastic_sell_v2_shadow", "sell", "core", 1, regime_policy="internal_ema50"),
    StrategyDefinition("core-stochastic-v3", "stochastic_sell_v3_adaptive_shadow", "sell", "core", 2, regime_policy="internal_ema50", operational=True, decision_history_bars=4000, regime_channels=("stochastic",)),
    StrategyDefinition("core-stochastic-v4", "stochastic_sell_v4_retest_shadow", "sell", "core", 3, regime_policy="internal_ema50", operational=True, decision_history_bars=4000, regime_channels=("stochastic",)),
    StrategyDefinition("core-breakout-short-v1", "breakout_short_v1_shadow", "sell", "core", 4, 80, "internal_ema50", True),
    StrategyDefinition("core-mean-reversion-sell-v1", "mean_reversion_sell_v1_shadow", "sell", "core", 5, regime_policy="internal_ema50", operational=True),
    StrategyDefinition("core-multitimeframe", "multitimeframe_trend_pullback", "buy", "core", 0, 1000, "internal_multitimeframe", decision_history_bars=1000),
    StrategyDefinition("core-multitimeframe-v2", "multitimeframe_trend_pullback_v2_shadow", "buy", "core", 1, 1000, "internal_multitimeframe", decision_history_bars=1000),
    StrategyDefinition("core-multitimeframe-v3", "multitimeframe_trend_pullback_v3_adaptive_shadow", "buy", "core", 2, 1000, "internal_multitimeframe", True, decision_history_bars=4000, regime_channels=("multitimeframe",)),
    StrategyDefinition("core-buy-trend-pullback-breakout-v1", "buy_trend_pullback_breakout_v1_shadow", "buy", "core", 3, 1000, "internal_multitimeframe", True, decision_history_bars=1000),
    StrategyDefinition("core-buy-trend-dip-stochastic-v1", "buy_trend_dip_stochastic_v1_shadow", "buy", "core", 4, 1000, "internal_multitimeframe", True, decision_history_bars=1000),
    StrategyDefinition("core-combined-v3", "portfolio_v3_adaptive_union_shadow", "combined", "portfolio", 0, 4000, "internal_portfolio", True, decision_history_bars=4000, regime_channels=("portfolio",), replay_session="combined"),
    StrategyDefinition("core-combined-v4", "portfolio_zigzag_v4_v51_stochastic_v4_shadow", "combined", "portfolio", 1, 4000, "internal_portfolio", decision_history_bars=4000, regime_channels=("portfolio",), replay_session="combined"),
)

STRATEGIES_BY_PROFILE = {definition.profile: definition for definition in STRATEGY_DEFINITIONS}
STRATEGIES_BY_BOT_ID = {definition.bot_id: definition for definition in STRATEGY_DEFINITIONS}
FAMILY_PRESENTATION_ORDER = {"scalp": 0, "sell": 1, "buy": 2, "combined": 3}


def strategy_definition(profile: str) -> StrategyDefinition | None:
    return STRATEGIES_BY_PROFILE.get(profile)


def strategy_presentation_order(profile: str) -> tuple[int, int, str]:
    """Stable public ordering shared by catalog, comparison and chart series."""
    definition = strategy_definition(profile)
    if definition is None:
        return 99, 99, profile.casefold()
    return FAMILY_PRESENTATION_ORDER[definition.family], definition.order, definition.profile


def operational_bot_ids() -> frozenset[str]:
    return frozenset(definition.bot_id for definition in STRATEGY_DEFINITIONS if definition.operational)


def validate_active_catalog(bots: Iterable[CatalogStrategy]) -> None:
    active = {bot.id: bot for bot in bots if bot.active}
    missing = set(active) - set(STRATEGIES_BY_BOT_ID)
    mismatched = {
        bot_id
        for bot_id, bot in active.items()
        if bot_id in STRATEGIES_BY_BOT_ID and STRATEGIES_BY_BOT_ID[bot_id].profile != bot.strategy_profile
    }
    if missing or mismatched:
        raise ValueError(
            "strategy catalog does not match registry: "
            f"unregistered={sorted(missing)} mismatched={sorted(mismatched)}"
        )
