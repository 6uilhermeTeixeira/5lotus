import os
import unittest
from unittest.mock import patch

from app.config import Settings


class BacktestBrokerCostDefaultsTests(unittest.TestCase):
    def test_fusion_zero_account_defaults_use_zero_spread_and_round_turn_commission(self) -> None:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"DAYTRADE_BACKTEST_SPREAD_POINTS", "DAYTRADE_BACKTEST_COMMISSION_PER_LOT"}
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings()

        self.assertEqual(settings.backtest_spread_points, 0)
        self.assertEqual(settings.backtest_commission_per_lot, 4.50)


if __name__ == "__main__":
    unittest.main()
