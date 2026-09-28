"""Build account and operational dashboard views without HTTP dependencies."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from ..schemas import (
    AccountDashboardResponse,
    AccountSnapshot,
    BotCatalogItem,
    OperationsResponse,
    RuntimeStatusItem,
)


def _optional_datetime(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value)) if value else None


def build_operations_response(
    bots: Sequence[BotCatalogItem],
    statuses: Sequence[Mapping[str, Any]],
    snapshots: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
) -> OperationsResponse:
    status_by_bot = {str(row.get("bot_id")): row for row in statuses}
    snapshot_by_bot = {str(row.get("bot_id")): row for row in snapshots}
    items: list[RuntimeStatusItem] = []
    for bot in bots:
        state = status_by_bot.get(bot.id, {})
        snapshot = snapshot_by_bot.get(bot.id, {})
        last_request = _optional_datetime(state.get("last_request_at_utc"))
        last_success = _optional_datetime(state.get("last_success_at_utc")) or last_request
        last_candle = _optional_datetime(state.get("last_candle_at_utc"))
        consecutive_errors = int(state.get("consecutive_errors") or 0)
        if consecutive_errors:
            health = "degraded"
        elif now.weekday() >= 5:
            health = "market_closed"
        elif last_success is None:
            health = "no_data"
        else:
            age_minutes = (now - last_success).total_seconds() / 60
            health = "healthy" if age_minutes <= 15 else "delayed" if age_minutes <= 30 else "stale"
        market_lag = max(0.0, (now - last_candle).total_seconds()) if last_candle else None
        items.append(RuntimeStatusItem(
            bot_id=bot.id,
            name=bot.name,
            status=health,
            last_request_at_utc=last_request,
            last_attempt_at_utc=state.get("last_attempt_at_utc"),
            last_success_at_utc=last_success,
            last_candle_at_utc=state.get("last_candle_at_utc"),
            last_action=state.get("last_action"),
            last_reason=state.get("last_reason"),
            last_latency_ms=state.get("last_latency_ms"),
            consecutive_errors=consecutive_errors,
            last_error=state.get("last_error"),
            last_error_code=state.get("last_error_code"),
            market_lag_seconds=market_lag,
            snapshot_updated_at_utc=snapshot.get("updated_at"),
            market_data_through_utc=snapshot.get("market_data_through_utc"),
        ))
    return OperationsResponse(updated_at_utc=now, bots=items)


def build_account_response(
    row: Mapping[str, Any] | None,
    *,
    expected_account_id: str,
    expected_server: str,
    initial_balance: float,
    now: datetime,
) -> AccountDashboardResponse:
    if row is None:
        return AccountDashboardResponse(
            available=False,
            status="waiting",
            initial_balance=initial_balance,
            expected_account_id=expected_account_id,
            expected_server=expected_server,
        )
    observed_at = datetime.fromisoformat(str(row["observed_at_utc"]))
    age_seconds = max(0.0, (now - observed_at).total_seconds())
    status = "online" if age_seconds <= 30 else "delayed" if age_seconds <= 120 else "offline"
    account = AccountSnapshot.model_validate(row)
    if account.account_id is None and expected_account_id:
        account = account.model_copy(update={"account_id": int(expected_account_id)})
    comparisons: list[bool] = []
    if expected_account_id:
        comparisons.append(expected_account_id == str(account.account_id or ""))
    if expected_server:
        comparisons.append(expected_server.casefold() == account.server.casefold())
    return AccountDashboardResponse(
        available=True,
        status=status,
        initial_balance=initial_balance,
        expected_account_id=expected_account_id,
        expected_server=expected_server,
        identity_matches=all(comparisons) if comparisons else None,
        account=account,
        observed_at_utc=observed_at,
        age_seconds=round(age_seconds, 1),
    )
