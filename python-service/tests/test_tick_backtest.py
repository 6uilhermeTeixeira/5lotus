import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backtest_happy_gold_tick_impulse import Position, update_position


class TickBacktestTests(unittest.TestCase):
    def test_buy_uses_bid_for_stop(self) -> None:
        position = Position("buy", 1_000, 100.0, 97.6, 110.0, 100.0, 100.0)
        closed = update_position(position, 2_000, 97.5, 98.0, mode="fixed", max_hold_seconds=180, commission=0)
        self.assertIsNotNone(closed)
        self.assertEqual(closed.exit_reason, "stop")
        self.assertEqual(closed.exit_price, 97.5)

    def test_managed_buy_moves_stop_to_break_even(self) -> None:
        position = Position("buy", 1_000, 100.0, 97.6, 110.0, 100.0, 100.0)
        self.assertIsNone(update_position(position, 2_000, 100.5, 100.6, mode="managed", max_hold_seconds=180, commission=0))
        self.assertEqual(position.stop, 100.0)

    def test_sell_time_exit_uses_ask(self) -> None:
        position = Position("sell", 1_000, 100.0, 102.4, 90.0, 100.0, -100.0)
        closed = update_position(position, 181_000, 99.0, 99.2, mode="fixed", max_hold_seconds=180, commission=0)
        self.assertIsNotNone(closed)
        self.assertEqual(closed.exit_reason, "time")
        self.assertEqual(closed.exit_price, 99.2)


if __name__ == "__main__":
    unittest.main()
