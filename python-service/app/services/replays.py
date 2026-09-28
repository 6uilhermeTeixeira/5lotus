"""Replay cache policies shared by the HTTP endpoints.

The service receives storage and dataset functions as dependencies.  This keeps
the policy independent from FastAPI and lets ``app.main`` retain its stable
compatibility wrappers for callers and tests.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from ..config import Settings
from ..local_dataset import DatasetRelease
from ..schemas import BotCatalogItem, CandleSnapshot, HistoricalReplayResponse
from ..supabase_store import SupabaseRequestError


class BacktestSnapshotStore(Protocol):
    def load_backtest_snapshot(self, bot_id: str, days: int) -> HistoricalReplayResponse | None: ...


def load_cached_backtest(
    settings: Settings,
    bot: BotCatalogItem,
    days: int,
    mode: str,
    *,
    uses_supabase: bool,
    store_factory: Callable[[Settings], BacktestSnapshotStore],
    local_loader: Callable[[Path, str, int], HistoricalReplayResponse | None],
) -> HistoricalReplayResponse | None:
    if uses_supabase:
        try:
            replay = store_factory(settings).load_backtest_snapshot(bot.id, days)
            if replay is not None:
                return replay
        except SupabaseRequestError as error:
            # Historical snapshots are immutable read models. Keep the research
            # portal available during a transient database outage, but never
            # hide authentication/configuration failures behind stale data.
            if not error.retryable and not (error.status_code is not None and error.status_code >= 500):
                raise
    cache_path = (
        settings.backtest_cache_path
        if mode == "normalized"
        else settings.backtest_cache_path.parent / "backtests-operational"
    )
    replay = local_loader(cache_path, bot.id, days)
    if replay is None and uses_supabase:
        replay = local_loader(settings.legacy_backtest_cache_path, bot.id, days)
    return replay


def scope_cached_replay(
    replay: HistoricalReplayResponse,
    days: int,
    *,
    results_builder: Callable,
) -> HistoricalReplayResponse:
    """Derive a shorter replay from a larger cache without changing trades."""
    cutoff = replay.period_end_utc - timedelta(days=days)
    trades = [trade for trade in replay.trades if trade.opened_at_utc >= cutoff]
    results = results_builder([trade.model_dump(mode="json") for trade in trades], "cached-replay")
    return replay.model_copy(update={
        "period_start_utc": max(replay.period_start_utc, cutoff),
        "summary": results.summary,
        "daily_pnl": results.daily_pnl,
        "trades": trades,
        "validation_folds": [fold for fold in replay.validation_folds if fold.period_end_utc > cutoff],
    })


def load_comparison_replay(
    bot: BotCatalogItem,
    days: int,
    mode: str,
    *,
    max_history_days: int,
    load_cached: Callable[[BotCatalogItem, int, str], HistoricalReplayResponse | None],
    scope_replay: Callable[[HistoricalReplayResponse, int], HistoricalReplayResponse],
    normalize_risk: Callable[[HistoricalReplayResponse], HistoricalReplayResponse],
) -> HistoricalReplayResponse | None:
    replay = load_cached(bot, days, mode)
    if replay is not None:
        return normalize_risk(replay) if mode == "normalized" and replay.risk_per_trade_pct != 1.0 else replay
    for available_days in (max_history_days, 365):
        if available_days <= days:
            continue
        replay = load_cached(bot, available_days, mode)
        if replay is not None:
            scoped = scope_replay(replay, days)
            return normalize_risk(scoped) if mode == "normalized" else scoped
    return None


def load_local_replay_with_candles(
    settings: Settings,
    bot: BotCatalogItem,
    days: int,
    *,
    load_cached: Callable[[BotCatalogItem, int, str], HistoricalReplayResponse | None],
    scope_replay: Callable[[HistoricalReplayResponse, int], HistoricalReplayResponse],
    dataset_open: Callable[[Path, str], DatasetRelease],
    chart_loader: Callable,
) -> HistoricalReplayResponse | None:
    replay = load_cached(bot, days, "normalized")
    if replay is None:
        annual = load_cached(bot, 365, "normalized")
        replay = scope_replay(annual, days) if annual is not None else None
    if replay is None:
        return None
    release = dataset_open(settings.lotus_data_root, "CURRENT")
    market_candles = chart_loader(
        release, bot.symbol.upper(), "5m", days, limit=settings.chart_cache_limit
    )
    candles = [
        CandleSnapshot(
            timestamp_utc=datetime.fromtimestamp(candle.t / 1000, tz=timezone.utc),
            open=candle.o,
            high=candle.h,
            low=candle.l,
            close=candle.c,
            volume=candle.volume,
        )
        for candle in market_candles
    ]
    return replay.model_copy(update={"candles": candles})
