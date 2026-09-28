from datetime import datetime, timedelta, timezone

from app.schemas import BotCatalogItem
from app.services.runtime import build_account_response, build_operations_response


NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)


def _bot() -> BotCatalogItem:
    return BotCatalogItem(
        id="core-test",
        name="Test Strategy",
        description="Runtime test",
        strategy_profile="test_profile",
        symbol="XAUUSD",
        timeframe="M5",
    )


def test_operations_classifies_latency_and_error_precedence() -> None:
    bot = _bot()
    delayed = (NOW - timedelta(minutes=20)).isoformat()
    candle = (NOW - timedelta(seconds=90)).isoformat()
    response = build_operations_response(
        [bot],
        [{"bot_id": bot.id, "last_success_at_utc": delayed, "last_candle_at_utc": candle}],
        [{"bot_id": bot.id, "updated_at": NOW.isoformat()}],
        now=NOW,
    )
    assert response.bots[0].status == "delayed"
    assert response.bots[0].market_lag_seconds == 90

    degraded = build_operations_response(
        [bot],
        [{"bot_id": bot.id, "last_success_at_utc": NOW.isoformat(), "consecutive_errors": 1}],
        [],
        now=NOW,
    )
    assert degraded.bots[0].status == "degraded"


def test_account_waiting_and_connected_identity() -> None:
    waiting = build_account_response(
        None,
        expected_account_id="466305",
        expected_server="FusionMarkets-Demo",
        initial_balance=100,
        now=NOW,
    )
    assert waiting.status == "waiting"
    assert not waiting.available

    row = {
        "account_id": 466305,
        "broker": "Fusion Markets",
        "server": "FusionMarkets-Demo",
        "currency": "USD",
        "trade_mode": "demo",
        "leverage": 500,
        "balance": 110,
        "equity": 111,
        "margin_free": 100,
        "floating_profit": 1,
        "realized_profit_today": 10,
        "profit_day": "2026-09-14",
        "observed_at_utc": (NOW - timedelta(seconds=5)).isoformat(),
    }
    connected = build_account_response(
        row,
        expected_account_id="466305",
        expected_server="FusionMarkets-Demo",
        initial_balance=100,
        now=NOW,
    )
    assert connected.status == "online"
    assert connected.identity_matches is True
    assert connected.age_seconds == 5
