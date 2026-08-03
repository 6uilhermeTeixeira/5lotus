"""Compute and persist compact historical replays for dashboard comparisons."""

from __future__ import annotations

import argparse
from collections import defaultdict

from app.backtest import run_historical_replay
from app.config import get_settings
from app.schemas import BotCatalogItem
from app.supabase_store import SupabaseStore


def _source_bot_id(bot: BotCatalogItem, default_symbol: str, default_bot_id: str) -> str:
    if bot.symbol.upper() == default_symbol.upper():
        return default_bot_id
    if bot.symbol.upper() == "EURUSD":
        return "bot-eur-1"
    if bot.symbol.upper() == "BTCUSD":
        return "bot-btc-13"
    return bot.id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", action="append", help="Symbol to process; repeat for more than one.")
    parser.add_argument("--bot-id", action="append", help="Optional bot filter; repeat for more than one.")
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365")

    settings = get_settings()
    store = SupabaseStore(settings)
    symbols = {value.upper() for value in args.symbol} if args.symbol else None
    bot_ids = set(args.bot_id) if args.bot_id else None
    bots = [
        bot for bot in store.list_bots()
        if (symbols is None or bot.symbol.upper() in symbols) and (bot_ids is None or bot.id in bot_ids)
    ]
    grouped: defaultdict[tuple[str, str, str], list[BotCatalogItem]] = defaultdict(list)
    for bot in bots:
        source_id = _source_bot_id(bot, settings.default_symbol, settings.backtest_market_data_bot_id)
        grouped[(bot.symbol, bot.timeframe, source_id)].append(bot)

    for (symbol, timeframe, source_id), market_bots in grouped.items():
        canonical = next((bot for bot in market_bots if bot.id == source_id), market_bots[0])
        candles = store.load_candles(canonical, settings.backtest_candle_limit, source_bot_id=source_id)
        if not candles:
            print(f"SKIP symbol={symbol} timeframe={timeframe} source={source_id} reason=no_candles", flush=True)
            continue
        print(f"MARKET symbol={symbol} timeframe={timeframe} source={source_id} candles={len(candles)}", flush=True)
        for bot in market_bots:
            replay = run_historical_replay(bot, candles, settings, days=args.days)
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
