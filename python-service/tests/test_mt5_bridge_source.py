from pathlib import Path
import unittest


class Mt5BridgeSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (
            Path(__file__).resolve().parents[2]
            / "mt5"
            / "experts"
            / "SyncLeadBridgeEA.mq5"
        ).read_text(encoding="utf-8")

    def test_uses_compose_shared_network_port(self) -> None:
        self.assertIn("http://127.0.0.1:1112/decision", self.source)
        self.assertIn("http://127.0.0.1:1112/api/trades", self.source)

    def test_polls_only_current_v3_catalog(self) -> None:
        for bot_id in (
            "core-zigzag-v3",
            "core-stochastic-v3",
            "core-multitimeframe-v3",
            "core-combined-v3",
        ):
            self.assertIn(bot_id, self.source)
        self.assertNotIn('input string StrategyBot1Id = "bot-', self.source)

    def test_execution_fails_closed_and_reports_positions(self) -> None:
        self.assertIn('input string ExecutionBotId = "";', self.source)
        self.assertIn('"positions\\":" + SerializePositions()', self.source)


if __name__ == "__main__":
    unittest.main()
