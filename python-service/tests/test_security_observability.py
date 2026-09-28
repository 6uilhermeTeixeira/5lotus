import hashlib
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import password_matches
from app.main import app, read_account
from app.schemas import AccountSnapshot, DecisionRequest, TickIngestRequest
from app.security import InMemoryRateLimiter, RateLimit
from app.supabase_store import SupabaseStore
from app.telemetry import emit_event, metrics_snapshot


class SecurityAndObservabilityTests(unittest.TestCase):
    def test_account_api_reports_connected_identity_and_profit(self) -> None:
        snapshot = {
            "account_id": 123456,
            "broker": "Fusion Markets",
            "server": "FusionMarkets-Demo",
            "currency": "USD",
            "trade_mode": "demo",
            "leverage": 500,
            "balance": 10100,
            "equity": 10125,
            "margin_free": 10000,
            "floating_profit": 25,
            "realized_profit_today": 100,
            "profit_day": "2026-09-10",
            "observed_at_utc": "2026-09-10T07:59:55+00:00",
        }
        with patch("app.main._require_api_session"), patch("app.main._uses_supabase_results", return_value=True), patch(
            "app.main.SupabaseStore"
        ) as store_type, patch("app.main.datetime") as clock, patch("app.main.settings.mt5_login", "123456"), patch(
            "app.main.settings.mt5_server", "FusionMarkets-Demo"
        ), patch("app.main.settings.mt5_initial_balance", 100):
            store_type.return_value.load_latest_account_snapshot.return_value = snapshot
            clock.fromisoformat.side_effect = datetime.fromisoformat
            clock.now.return_value = datetime(2026, 9, 10, 8, tzinfo=timezone.utc)
            result = read_account(MagicMock())

        self.assertTrue(result.available)
        self.assertEqual(result.status, "online")
        self.assertTrue(result.identity_matches)
        self.assertEqual(result.account.floating_profit, 25)
        self.assertEqual(result.initial_balance, 100)

    def test_health_and_readiness_have_distinct_contracts(self) -> None:
        client = TestClient(app)
        health = client.get("/health")
        ready = client.get("/ready")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["status"], "ready")
        self.assertIn("Content-Security-Policy", health.headers)

    def test_cross_site_authenticated_mutation_is_blocked(self) -> None:
        response = TestClient(app).post("/logout", headers={"Origin": "https://attacker.example"})
        self.assertEqual(response.status_code, 403)

    def test_rate_limiter_rejects_attempt_over_limit(self) -> None:
        limiter = InMemoryRateLimiter()
        limiter.check("login:local", RateLimit(1, 60))
        with self.assertRaises(HTTPException) as context:
            limiter.check("login:local", RateLimit(1, 60))
        self.assertEqual(context.exception.status_code, 429)

    def test_scrypt_password_format_is_supported(self) -> None:
        salt = b"0123456789abcdef"
        digest = hashlib.scrypt(b"correct horse", salt=salt, n=2**14, r=8, p=1).hex()
        settings = SimpleNamespace(dashboard_password=f"scrypt${salt.hex()}${digest}")
        self.assertTrue(password_matches("correct horse", settings))
        self.assertFalse(password_matches("wrong", settings))

    def test_invalid_market_snapshot_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DecisionRequest(
                request_id="invalid-market",
                timestamp_utc="2026-08-04T00:00:00Z",
                symbol="XAUUSD",
                timeframe="M5",
                bid=100,
                ask=99,
                spread_points=-1,
                point_size=0.01,
                value_per_point_per_lot=1,
                account=AccountSnapshot(balance=10000, equity=10000, margin_free=10000),
            )

    def test_non_finite_impulse_indicator_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DecisionRequest(
                request_id="invalid-indicator",
                timestamp_utc="2026-08-04T00:00:00Z",
                symbol="XAUUSD",
                timeframe="M5",
                bid=3000,
                ask=3000.1,
                spread_points=10,
                point_size=0.01,
                value_per_point_per_lot=1,
                account=AccountSnapshot(balance=10000, equity=10000, margin_free=10000),
                indicators={"impulse_30s_move_points": float("nan")},
            )

    def test_tick_batch_requires_ordered_unique_valid_quotes(self) -> None:
        with self.assertRaises(ValidationError):
            TickIngestRequest(
                collector_id="forward-01",
                symbol="XAUUSD",
                point_size=0.01,
                ticks=[
                    {"time_msc": 2000, "sequence": 2, "bid": 2000, "ask": 2001},
                    {"time_msc": 1000, "sequence": 1, "bid": 2000, "ask": 1999},
                ],
            )

    def test_metrics_are_aggregated_without_run_id_label(self) -> None:
        emit_event(run_id="request-sensitive-123", step="test_step", status="passed", duration_ms=12)
        snapshot = metrics_snapshot()
        self.assertTrue(any(item["step"] == "test_step" for item in snapshot["counters"]))
        self.assertNotIn("request-sensitive-123", str(snapshot))

    def test_supabase_retries_a_transient_read(self) -> None:
        settings = SimpleNamespace(
            supabase_results_configured=True,
            supabase_url="https://project.supabase.co",
            supabase_service_role_key="not-a-real-key",
            supabase_retry_attempts=2,
            supabase_timeout_seconds=0.1,
        )
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"[]"
        with patch("app.supabase_store.urlopen", side_effect=[URLError("temporary"), response]) as mocked, patch("app.supabase_store.time.sleep"):
            result = SupabaseStore(settings)._request("bots?select=id")
        self.assertEqual(result, [])
        self.assertEqual(mocked.call_count, 2)


if __name__ == "__main__":
    unittest.main()
