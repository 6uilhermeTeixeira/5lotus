import unittest

from app.pages import render_comparison_page
from app.schemas import BotCatalogItem


class ComparisonPageTests(unittest.TestCase):
    def test_comparison_page_renders_three_independent_bots(self) -> None:
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
            ]
        ]

        response = render_comparison_page(bots)
        html = bytes(response.body).decode("utf-8")

        self.assertIn("Estratégias simultâneas", html)
        self.assertIn("Bot 1 — Fimath", html)
        self.assertIn("Bot 2 — Momentum ATR", html)
        self.assertIn("Bot 3 — RSI Bollinger", html)
        self.assertIn("/api/compare", html)


if __name__ == "__main__":
    unittest.main()
