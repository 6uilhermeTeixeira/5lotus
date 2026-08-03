import unittest

from app.pages import render_catalog_page, render_comparison_page, render_results_page
from app.schemas import BotCatalogItem


class ComparisonPageTests(unittest.TestCase):
    def test_catalog_separates_active_and_archived_strategies(self) -> None:
        active_bots = [
            BotCatalogItem(id=f"bot-{index}", name=name, description="Teste", strategy_profile="fimath_ema20_flow", symbol="XAUUSD", timeframe="M5")
            for index, name in [(6, "Stochastic Sell 18 UTC"), (7, "Tendência Multitemporal"), (11, "Portfólio 7/6 · 100/75"), (12, "Happy Gold ZigZag Scalper"), (13, "Happy Gold ZigZag · Confirmação de Regime")]
        ]
        archived_bots = [
            BotCatalogItem(id="bot-1", name="Fimath", description="Teste", strategy_profile="fimath_ema20_flow", symbol="XAUUSD", timeframe="M5", active=False),
            BotCatalogItem(id="bot-eur-1", name="Fimath · EUR/USD", description="Teste", strategy_profile="fimath_ema20_flow", symbol="EURUSD", timeframe="M5", active=False),
        ]

        html = bytes(render_catalog_page(active_bots, archived_bots).body).decode("utf-8")

        self.assertIn('data-catalog-tab="active"', html)
        self.assertIn('data-catalog-tab="archived"', html)
        self.assertIn('data-catalog-panel="archived"', html)
        self.assertIn('id="equity-chart"', html)
        self.assertIn("/api/equity-comparison?symbol=XAUUSD", html)
        self.assertIn("Happy Gold ZigZag Scalper", html)
        self.assertIn("Fimath · EUR/USD", html)
        self.assertIn("Ver histórico", html)
        self.assertEqual(html.count('class="bot card"'), 7)

    def test_comparison_page_renders_five_active_bots(self) -> None:
        bots = [
            BotCatalogItem(
                id=f"bot-{index}",
                name=name,
                description="Teste",
                strategy_profile=profile,
                symbol="XAUUSD",
                timeframe="M5",
            )
            for index, name, profile in [
                (6, "Stochastic Sell 18 UTC", "stochastic_sell_session"),
                (7, "Tendência Multitemporal", "multitimeframe_trend_pullback"),
                (11, "Portfólio 7/6 · 100/75", "portfolio_6_7_100_75"),
                (12, "Happy Gold ZigZag Scalper", "happy_gold_zigzag_scalper"),
                (13, "Happy Gold ZigZag · Confirmação de Regime", "happy_gold_zigzag_regime_confirmed"),
            ]
        ]

        response = render_comparison_page(bots)
        html = bytes(response.body).decode("utf-8")

        self.assertIn("Estratégias ativas", html)
        self.assertIn("Stochastic Sell 18 UTC", html)
        self.assertIn("Tendência Multitemporal", html)
        self.assertIn("Portfólio 7/6 · 100/75", html)
        self.assertIn("Happy Gold ZigZag Scalper", html)
        self.assertIn("Happy Gold ZigZag · Confirmação de Regime", html)
        self.assertIn("<strong>5</strong>", html)
        self.assertIn("/api/compare", html)

    def test_results_page_defaults_to_long_historical_validation(self) -> None:
        bot = BotCatalogItem(
            id="bot-4",
            name="MACD Trend",
            description="Teste",
            strategy_profile="macd_trend_crossover",
            symbol="XAUUSD",
            timeframe="M5",
        )

        html = bytes(render_results_page(bot).body).decode("utf-8")

        self.assertIn("Validação histórica", html)
        self.assertIn('<option value="120">120 dias</option>', html)
        self.assertIn('<option value="365" selected>365 dias</option>', html)
        self.assertIn("/api/bots/bot-4/historical-replay?days=", html)
        self.assertIn("Preço e eventos simulados", html)
        self.assertIn("Premissas do replay", html)


if __name__ == "__main__":
    unittest.main()
