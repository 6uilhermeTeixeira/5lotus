"""Compute and persist compact historical replays for dashboard comparisons."""

from __future__ import annotations

import argparse
from collections import defaultdict

from app.backtest import run_historical_replay
from app.config import get_settings
from app.history_sync import TICK_INDICATOR_PROFILES, load_m5_candles, load_tick_indicators
from app.local_backtest_store import save_local_backtest
from app.local_dataset import DatasetRelease
from app.results_store import load_bots_catalog
from app.risk_normalization import normalize_replay_risk
from app.schemas import BotCatalogItem
from app.supabase_store import SupabaseStore
from app.strategy import ADAPTIVE_V3_COMBINED_PROFILE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", action="append", help="Symbol to process; repeat for more than one.")
    parser.add_argument("--bot-id", action="append", help="Optional bot filter; repeat for more than one.")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument(
        "--source", choices=("local", "supabase"), default="local",
        help="Canonical candle source. Local immutable releases are the default.",
    )
    parser.add_argument("--local-only", action="store_true", help="Do not replicate snapshots to Supabase.")
    args = parser.parse_args()
    if not 1 <= args.days <= 1095:
        parser.error("--days must be between 1 and 1095")

    settings = get_settings()
    store = SupabaseStore(settings) if settings.supabase_results_configured else None
    symbols = {value.upper() for value in args.symbol} if args.symbol else None
    bot_ids = set(args.bot_id) if args.bot_id else None
    bots = [
        bot for bot in load_bots_catalog(settings.bots_catalog_path)
        if bot.active
        if (symbols is None or bot.symbol.upper() in symbols) and (bot_ids is None or bot.id in bot_ids)
    ]
    grouped: defaultdict[tuple[str, str], list[BotCatalogItem]] = defaultdict(list)
    for bot in bots:
        grouped[(bot.symbol, bot.timeframe)].append(bot)

    for (symbol, timeframe), market_bots in grouped.items():
        if args.source == "local":
            if timeframe.upper() != "M5":
                print(f"SKIP symbol={symbol} timeframe={timeframe} reason=unsupported_local_timeframe", flush=True)
                continue
            release = DatasetRelease.open(settings.lotus_data_root, settings.lotus_dataset_version)
            candles = load_m5_candles(release, symbol.upper(), args.days)
            indicators = (
                load_tick_indicators(release, symbol.upper(), candles)
                if any(bot.strategy_profile in TICK_INDICATOR_PROFILES for bot in market_bots)
                else {}
            )
            dataset_version = release.version
        else:
            if store is None:
                raise RuntimeError("Supabase candle source is not configured")
            candles = store.load_candles(market_bots[0], settings.backtest_candle_limit)
            indicators = {}
            dataset_version = "supabase"
        if not candles:
            print(f"SKIP symbol={symbol} timeframe={timeframe} reason=no_candles", flush=True)
            continue
        print(
            f"MARKET symbol={symbol} timeframe={timeframe} candles={len(candles)} dataset={dataset_version}",
            flush=True,
        )
        for bot in market_bots:
            replay = run_historical_replay(
                bot, candles, settings, days=args.days, indicators_by_timestamp=indicators
            )
            operational_path = settings.backtest_cache_path.parent / "backtests-operational"
            save_local_backtest(operational_path, replay, args.days)
            if bot.strategy_profile != ADAPTIVE_V3_COMBINED_PROFILE:
                save_local_backtest(settings.backtest_cache_path, normalize_replay_risk(replay), args.days)
            if store is not None and not args.local_only:
                store.save_backtest_snapshot(replay, args.days)
            summary = replay.summary
            print(
                f"BOT id={bot.id} trades={summary.trades_count} win_rate={summary.win_rate_pct:.2f} "
                f"net={summary.net_pnl:.2f} profit_factor={summary.profit_factor:.2f} "
                f"validation={replay.validation_status}",
                flush=True,
            )


if __name__ == "__main__":
    main()
