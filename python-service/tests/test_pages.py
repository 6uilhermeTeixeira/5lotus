import unittest

from app.pages import render_catalog_page, render_comparison_page, render_results_page
from app.schemas import BotCatalogItem


class ComparisonPageTests(unittest.TestCase):
    def test_catalog_switches_between_symbols_and_renders_equity_chart(self) -> None:
        bots = [
            BotCatalogItem(id=f"bot-{symbol.lower()}-{index}", name=f"Bot {index} {symbol}", description="Teste", strategy_profile="fimath_ema20_flow", symbol=symbol, timeframe="M5")
            for symbol in ("XAUUSD", "EURUSD") for index in range(1, 8)
        ]

        html = bytes(render_catalog_page(bots).body).decode("utf-8")

        self.assertIn('data-symbol-toggle="XAUUSD"', html)
        self.assertIn('data-symbol-toggle="EURUSD"', html)
        self.assertIn('id="equity-chart"', html)
        self.assertIn("/api/equity-comparison?symbol=", html)
        self.assertEqual(html.count('class="bot card"'), 14)

    def test_comparison_page_renders_seven_independent_bots(self) -> None:
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
                (1, "Bot 1 — Fimath", "fimath_ema20_flow"),
                (2, "Bot 2 — Momentum ATR", "momentum_atr_breakout"),
                (3, "Bot 3 — RSI Bollinger", "rsi_bollinger_reversion"),
                (4, "Bot 4 — MACD Trend", "macd_trend_crossover"),
                (5, "Bot 5 — Stochastic Pullback", "stochastic_trend_pullback"),
                (6, "Bot 6 — Stochastic Sell 18 UTC", "stochastic_sell_session"),
                (7, "Bot 7 — Tendência Multitemporal", "multitimeframe_trend_pullback"),
            ]
        ]

        response = render_comparison_page(bots)
        html = bytes(response.body).decode("utf-8")

        self.assertIn("Estratégias simultâneas", html)
        self.assertIn("Bot 1 — Fimath", html)
        self.assertIn("Bot 2 — Momentum ATR", html)
        self.assertIn("Bot 3 — RSI Bollinger", html)
        self.assertIn("Bot 4 — MACD Trend", html)
        self.assertIn("Bot 5 — Stochastic Pullback", html)
        self.assertIn("Bot 6 — Stochastic Sell 18 UTC", html)
        self.assertIn("Bot 7 — Tendência Multitemporal", html)
        self.assertIn("<strong>7</strong>", html)
        self.assertIn("/api/compare", html)

    def test_results_page_defaults_to_long_historical_validation(self) -> None:
        bot = BotCatalogItem(
            id="bot-4",
            name="Bot 4 — MACD Trend",
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
