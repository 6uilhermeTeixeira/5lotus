import unittest

import numpy as np

from app.strategies.zigzag_v4_research import exit_trade, persistence


class TickResearchTests(unittest.TestCase):
    def test_adverse_gap_fills_beyond_stop(self):
        t = np.array([0, 100, 200])
        bid = np.array([100., 96., 95.])
        row = exit_trade(t, bid, bid+.1, 0, 1, stop=2.4, slippage=0)
        self.assertEqual(row['exit_ms'], 100)
        self.assertLess(row['r'], -1)

    def test_trailing_cannot_retroactively_exit_on_its_trigger_quote(self):
        t = np.array([0, 100, 200])
        bid = np.array([100., 102., 101.])
        row = exit_trade(t, bid, bid, 0, 1, stop=2.4, slippage=0)
        self.assertEqual(row['exit_ms'], 200)
        self.assertEqual(row['exit_reason'], 'stop')
        self.assertAlmostEqual(row['net_pnl'], 9.55)

    def test_short_exit_uses_ask(self):
        t = np.array([0, 100])
        bid = np.array([100., 99.])
        ask = np.array([100.2, 99.2])
        row = exit_trade(t, bid, ask, 0, -1, stop=2.4, slippage=0, hold_ms=100)
        self.assertAlmostEqual(row['net_pnl'], 7.55)

    def test_time_exit_uses_first_quote_at_or_after_deadline(self):
        t = np.array([0, 59000, 61000])
        bid = np.array([100., 100.1, 100.2])
        row = exit_trade(t, bid, bid, 0, 1, stop=2.4, slippage=0, hold_ms=60000)
        self.assertEqual(row['exit_ms'], 61000)

    def test_confirmation_resets_on_recross_and_new_bar(self):
        t = np.array([0, 200, 500, 700, 900, 1200])
        mask = np.array([True, True, False, True, True, True])
        bucket = np.array([0, 0, 0, 0, 0, 1])
        np.testing.assert_array_equal(persistence(t, mask, bucket), [0, 200, 0, 0, 200, 0])

    def test_future_quotes_do_not_change_past_confirmation(self):
        t = np.array([0, 100, 200, 300, 400])
        mask = np.array([False, True, True, False, True])
        bucket = np.zeros(5)
        np.testing.assert_array_equal(persistence(t, mask, bucket)[:3], persistence(t[:3], mask[:3], bucket[:3]))


if __name__ == '__main__':
    unittest.main()
