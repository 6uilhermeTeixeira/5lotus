import json
import unittest
from pathlib import Path

from app.schemas import BotCatalogItem
from app.strategies.registry import (
    STRATEGY_DEFINITIONS,
    STRATEGIES_BY_BOT_ID,
    STRATEGIES_BY_PROFILE,
    operational_bot_ids,
    validate_active_catalog,
)


class StrategyRegistryTests(unittest.TestCase):
    def test_every_active_catalog_strategy_is_registered(self) -> None:
        catalog_path = Path(__file__).parents[1] / "data" / "bots.json"
        bots = [BotCatalogItem.model_validate(row) for row in json.loads(catalog_path.read_text(encoding="utf-8"))]

        self.assertEqual(
            {bot.id for bot in bots if bot.active},
            set(STRATEGIES_BY_BOT_ID),
        )
        for bot in bots:
            if bot.active:
                self.assertEqual(STRATEGIES_BY_BOT_ID[bot.id].profile, bot.strategy_profile)

    def test_registry_keys_are_unique(self) -> None:
        self.assertEqual(len(STRATEGY_DEFINITIONS), len(STRATEGIES_BY_BOT_ID))
        self.assertEqual(len(STRATEGY_DEFINITIONS), len(STRATEGIES_BY_PROFILE))

    def test_operational_set_is_derived_from_registry(self) -> None:
        expected = {definition.bot_id for definition in STRATEGY_DEFINITIONS if definition.operational}

        self.assertEqual(set(operational_bot_ids()), expected)

    def test_catalog_validation_fails_closed_on_profile_drift(self) -> None:
        catalog_path = Path(__file__).parents[1] / "data" / "bots.json"
        bots = [BotCatalogItem.model_validate(row) for row in json.loads(catalog_path.read_text(encoding="utf-8"))]
        changed = [
            bot.model_copy(update={"strategy_profile": "unexpected_profile"}) if bot.id == "core-stochastic-v3" else bot
            for bot in bots
        ]

        with self.assertRaisesRegex(ValueError, "mismatched=.*core-stochastic-v3"):
            validate_active_catalog(changed)

    def test_history_requirements_cover_each_family(self) -> None:
        self.assertEqual(STRATEGIES_BY_PROFILE["breakout_short_v1_shadow"].history_bars, 80)
        self.assertEqual(STRATEGIES_BY_PROFILE["multitimeframe_trend_pullback_v3_adaptive_shadow"].history_bars, 1000)
        self.assertEqual(STRATEGIES_BY_PROFILE["portfolio_v3_adaptive_union_shadow"].history_bars, 4000)
        self.assertFalse(STRATEGIES_BY_PROFILE["zigzag_scalper_v7_directional_shadow"].replay_supported)
        self.assertFalse(STRATEGIES_BY_PROFILE["zigzag_scalper_v12_micro_retest_shadow"].replay_supported)
        self.assertTrue(STRATEGIES_BY_PROFILE["zigzag_scalper_v13_m30_close_shadow"].replay_supported)

    def test_runtime_context_is_declared_with_the_strategy(self) -> None:
        stochastic = STRATEGIES_BY_PROFILE["stochastic_sell_v3_adaptive_shadow"]
        multitimeframe = STRATEGIES_BY_PROFILE["multitimeframe_trend_pullback_v3_adaptive_shadow"]
        portfolio = STRATEGIES_BY_PROFILE["portfolio_v3_adaptive_union_shadow"]

        self.assertEqual(stochastic.decision_history_bars, 4000)
        self.assertEqual(stochastic.regime_channels, ("stochastic",))
        self.assertEqual(multitimeframe.regime_channels, ("multitimeframe",))
        self.assertEqual(portfolio.regime_channels, ("portfolio",))
        self.assertEqual(portfolio.replay_session, "combined")


if __name__ == "__main__":
    unittest.main()
