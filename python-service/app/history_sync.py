"""Publish downloaded Dukascopy data and refresh dashboard backtests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from bisect import bisect_right
import os
import subprocess
from threading import Lock

import duckdb

from .backtest import run_historical_replay
from .local_dataset import DatasetError, DatasetRelease
from .local_backtest_store import save_local_backtest
from .risk_normalization import normalize_replay_risk
from .results_store import load_bots_catalog
from .schemas import CandleSnapshot, HistoryRefreshResponse, MarketCandlePoint
from .supabase_store import SupabaseStore


class HistoryRefreshInProgress(RuntimeError):
    pass


_refresh_lock = Lock()
SUPPORTED_RESOLUTIONS = {"1m", "5m", "1h", "1d"}
TICK_INDICATOR_WINDOWS = (5, 10, 30, 60, 300, 900)
TICK_INDICATOR_PROFILES = {
    "happy_gold_tick_impulse_shadow",
    "happy_gold_zigzag_tick_context_shadow",
    "happy_gold_zigzag_structural_tick_shadow",
    "happy_gold_zigzag_normalized_range_shadow",
    "zigzag_scalper_v2_shadow",
    "zigzag_scalper_v3_adaptive_shadow",
    "zigzag_scalper_v4_tick_microstructure_shadow",
    "happy_gold_multiwindow_tick_score_shadow",
}


def publish_downloaded_history(settings, symbol: str, days: int) -> None:
    project_root = settings.lotus_publisher_script.parent.parent
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    source_path = str(project_root / "src")
    environment["PYTHONPATH"] = f"{source_path}:{existing_pythonpath}" if existing_pythonpath else source_path
    command = [
        str(settings.lotus_publisher_python),
        str(settings.lotus_publisher_script),
        "--instrument",
        symbol,
        "--requested-start",
        (datetime.now(timezone.utc).date() - timedelta(days=days - 1)).isoformat(),
        "--requested-end",
        (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
    ]
    try:
        subprocess.run(
            command,
            cwd=project_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.lotus_publish_timeout_seconds,
        )
    except FileNotFoundError as error:
        raise DatasetError("publicador 1lotus não está disponível") from error
    except subprocess.TimeoutExpired as error:
        raise DatasetError("publicação do histórico excedeu o tempo limite") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "falha desconhecida").strip().splitlines()[-1]
        raise DatasetError(f"falha ao publicar histórico: {detail[:300]}") from error


def load_m5_candles(release: DatasetRelease, symbol: str, days: int) -> list[CandleSnapshot]:
    if str(release.manifest.get("instrument", "")).upper() != symbol:
        raise DatasetError(f"dataset ativo não corresponde a {symbol}")
    coverage_end = release.manifest.get("coverage_end")
    if not isinstance(coverage_end, str):
        raise DatasetError("dataset não informa o fim da cobertura")
    cutoff = date.fromisoformat(coverage_end) - timedelta(days=days - 1)
    aggregations = release.manifest.get("aggregations", {})
    rows = aggregations.get("5m", []) if isinstance(aggregations, dict) else []
    paths = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            continue
        partition_day = row.get("day")
        if not isinstance(partition_day, str) or date.fromisoformat(partition_day) < cutoff:
            continue
        path = (release.root / row["path"]).resolve()
        if not path.is_relative_to(release.root) or not path.is_file():
            raise DatasetError(f"agregação M5 ausente ou fora da raiz: {row['path']}")
        paths.append(str(path))
    if not paths:
        raise DatasetError("nenhuma agregação M5 disponível no período")

    connection = duckdb.connect(":memory:")
    try:
        result = connection.execute(
            """SELECT t,o,h,l,c,coalesce(bid_volume,0)+coalesce(ask_volume,0)
               FROM read_parquet(?) ORDER BY t""",
            [paths],
        ).fetchall()
    finally:
        connection.close()
    return [
        CandleSnapshot(
            timestamp_utc=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )
        for timestamp_ms, open_price, high_price, low_price, close_price, volume in result
    ]


def load_chart_candles(
    release: DatasetRelease, symbol: str, resolution: str, days: int, *, limit: int = 50_000
) -> list[MarketCandlePoint]:
    if resolution not in SUPPORTED_RESOLUTIONS:
        raise DatasetError(f"resolução não suportada: {resolution}")
    if str(release.manifest.get("instrument", "")).upper() != symbol:
        raise DatasetError(f"dataset ativo não corresponde a {symbol}")
    coverage_end = release.manifest.get("coverage_end")
    if not isinstance(coverage_end, str):
        raise DatasetError("dataset não informa o fim da cobertura")
    cutoff = date.fromisoformat(coverage_end) - timedelta(days=days - 1)
    cutoff_ms = int(datetime.combine(cutoff, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
    aggregations = release.manifest.get("aggregations", {})
    rows = aggregations.get(resolution, []) if isinstance(aggregations, dict) else []
    paths: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            continue
        partition_day = row.get("day")
        if not isinstance(partition_day, str) or date.fromisoformat(partition_day) < cutoff:
            continue
        path = (release.root / row["path"]).resolve()
        if not path.is_relative_to(release.root) or not path.is_file():
            raise DatasetError(f"agregação ausente ou fora da raiz: {row['path']}")
        paths.append(str(path))
    if not paths:
        return []
    connection = duckdb.connect(":memory:")
    try:
        result = connection.execute(
            """SELECT * FROM (
                   SELECT t,o,h,l,c,coalesce(bid_volume,0)+coalesce(ask_volume,0) AS volume
                   FROM read_parquet(?) WHERE t >= ? ORDER BY t DESC LIMIT ?
               ) ordered_rows ORDER BY t""",
            [paths, cutoff_ms, limit],
        ).fetchall()
    finally:
        connection.close()
    return [
        MarketCandlePoint(t=t, o=o, h=h, l=low_price, c=c, volume=volume)
        for t, o, h, low_price, c, volume in result
    ]


def load_tick_indicators(
    release: DatasetRelease,
    symbol: str,
    candles: list[CandleSnapshot],
) -> dict[int, dict[str, float]]:
    """Build causal impulse features at each M5 close from published 1-second bars."""
    if not candles:
        return {}
    if str(release.manifest.get("instrument", "")).upper() != symbol.upper():
        raise DatasetError(f"dataset ativo não corresponde a {symbol}")
    if candles[-1].timestamp_utc - candles[0].timestamp_utc > timedelta(days=14):
        features: dict[int, dict[str, float]] = {}
        chunk: list[CandleSnapshot] = []
        chunk_start = candles[0].timestamp_utc
        for candle in candles:
            if chunk and candle.timestamp_utc >= chunk_start + timedelta(days=14):
                features.update(load_tick_indicators(release, symbol, chunk))
                chunk = []
                chunk_start = candle.timestamp_utc
            chunk.append(candle)
        features.update(load_tick_indicators(release, symbol, chunk))
        return features
    start_day = (candles[0].timestamp_utc - timedelta(seconds=max(TICK_INDICATOR_WINDOWS))).date()
    end_day = candles[-1].timestamp_utc.date()
    aggregations = release.manifest.get("aggregations", {})
    rows = aggregations.get("1s", []) if isinstance(aggregations, dict) else []
    paths: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            continue
        partition_day = row.get("day")
        if not isinstance(partition_day, str) or not start_day <= date.fromisoformat(partition_day) <= end_day:
            continue
        path = (release.root / row["path"]).resolve()
        if not path.is_relative_to(release.root) or not path.is_file():
            raise DatasetError(f"agregação 1s ausente ou fora da raiz: {row['path']}")
        paths.append(str(path))
    if not paths:
        return {}

    connection = duckdb.connect(":memory:")
    try:
        columns = {
            str(row[0])
            for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [paths]).fetchall()
        }
        activity_expression = "coalesce(tick_count,0)" if "tick_count" in columns else "1.0"
        spread_expression = "coalesce(spread_mean,0)" if "spread_mean" in columns else "0.0"
        rows = connection.execute(
            f"SELECT t,c,{activity_expression} AS activity,{spread_expression} AS spread FROM read_parquet(?) ORDER BY t",
            [paths],
        ).fetchall()
    finally:
        connection.close()
    timestamps = [int(row[0]) for row in rows]
    closes = [float(row[1]) for row in rows]
    activity = [float(row[2]) for row in rows]
    spreads = [float(row[3]) for row in rows]
    features: dict[int, dict[str, float]] = {}
    for candle in candles:
        candle_end_ms = int((candle.timestamp_utc + timedelta(minutes=5)).timestamp() * 1000)
        current_index = bisect_right(timestamps, candle_end_ms - 1) - 1
        if current_index < 0:
            continue
        item: dict[str, float] = {}
        for seconds in TICK_INDICATOR_WINDOWS:
            prior_index = bisect_right(timestamps, candle_end_ms - seconds * 1000) - 1
            ready = prior_index >= 0 and timestamps[prior_index] >= candle_end_ms - (seconds + 2) * 1000
            item[f"impulse_{seconds}s_ready"] = 1.0 if ready else 0.0
            item[f"impulse_{seconds}s_move_points"] = (
                (closes[current_index] - closes[prior_index]) / 0.01 if ready else 0.0
            )
            if ready:
                window = closes[prior_index:current_index + 1]
                realized_path = sum(abs(current - previous) for previous, current in zip(window, window[1:]))
                net_move = abs(closes[current_index] - closes[prior_index])
                item[f"micro_{seconds}s_range_points"] = (max(window) - min(window)) / 0.01
                item[f"micro_{seconds}s_efficiency"] = net_move / realized_path if realized_path else 0.0
                item[f"micro_{seconds}s_activity"] = sum(activity[prior_index:current_index + 1]) / seconds
                window_spreads = [value for value in spreads[prior_index:current_index + 1] if value > 0]
                item[f"micro_{seconds}s_mean_spread_pips"] = (
                    sum(window_spreads) / len(window_spreads) / 0.01 if window_spreads else 0.0
                )
            else:
                item[f"micro_{seconds}s_range_points"] = 0.0
                item[f"micro_{seconds}s_efficiency"] = 0.0
                item[f"micro_{seconds}s_activity"] = 0.0
                item[f"micro_{seconds}s_mean_spread_pips"] = 0.0
        activity_5s = item.get("micro_5s_activity", 0.0)
        activity_10s = item.get("micro_10s_activity", 0.0)
        item["micro_tick_acceleration_5s_vs_10s"] = activity_5s / activity_10s if activity_10s else 0.0
        features[candle_end_ms] = item
    return features


def refresh_history(settings, symbol: str = "XAUUSD", days: int = 365) -> HistoryRefreshResponse:
    normalized_symbol = symbol.upper()
    if not _refresh_lock.acquire(blocking=False):
        raise HistoryRefreshInProgress("uma atualização de histórico já está em andamento")
    try:
        publish_downloaded_history(settings, normalized_symbol, days)
        release = DatasetRelease.open(settings.lotus_data_root, "CURRENT")
        candles = load_m5_candles(release, normalized_symbol, days)
        uses_supabase = settings.results_store == "SUPABASE"
        store = SupabaseStore(settings) if uses_supabase else None
        catalog = store.list_bots() if store is not None else [
            bot for bot in load_bots_catalog(settings.bots_catalog_path) if bot.active
        ]
        bots = [
            bot for bot in catalog
            if bot.symbol.upper() == normalized_symbol and bot.timeframe.upper() == "M5"
        ]
        if not bots:
            raise DatasetError(f"nenhuma estratégia M5 ativa para {normalized_symbol}")
        tick_indicators = (
            load_tick_indicators(release, normalized_symbol, candles)
            if any(bot.strategy_profile in TICK_INDICATOR_PROFILES for bot in bots)
            else {}
        )
        if store is not None:
            store.upsert_candles(bots[0].id, normalized_symbol, "M5", candles)
        for bot in bots:
            replay = run_historical_replay(
                bot, candles, settings, days=days, indicators_by_timestamp=tick_indicators
            )
            if store is not None:
                store.save_backtest_snapshot(replay, days)
            else:
                operational_path = settings.backtest_cache_path.parent / "backtests-operational"
                save_local_backtest(operational_path, replay, days)
                if bot.strategy_profile != "portfolio_v3_adaptive_union_shadow":
                    save_local_backtest(settings.backtest_cache_path, normalize_replay_risk(replay), days)

        collection = release.manifest.get("collection", {})
        progress = float(collection.get("progress_pct", 0)) if isinstance(collection, dict) else 0.0
        return HistoryRefreshResponse(
            dataset_version=release.version,
            symbol=normalized_symbol,
            timeframe="M5",
            period_days=days,
            coverage_start=candles[0].timestamp_utc.date(),
            coverage_end=candles[-1].timestamp_utc.date(),
            collection_progress_pct=progress,
            candles_imported=len(candles),
            snapshots_updated=len(bots),
            updated_at_utc=datetime.now(timezone.utc),
        )
    finally:
        _refresh_lock.release()
