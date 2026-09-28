"""Build the causal OHLC replay for ZigZag Scalper V1.3.

The replay uses the local Dukascopy-derived M5 research candles.  V1.3 is
evaluated through the normal decision engine: a completed M30 close must cross
a confirmed fractal and the request must fall in the first M5 after that close.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

from app.backtest import run_historical_replay
from app.config import get_settings
from app.local_backtest_store import save_local_backtest
from app.results_store import load_bots_catalog
from app.schemas import CandleSnapshot


ROOT = Path(__file__).resolve().parents[1]
BOT_ID = "core-zigzag-v13"


def load_local_candles() -> list[CandleSnapshot]:
    rows: dict[str, CandleSnapshot] = {}
    for path in sorted((ROOT / "data" / "research").glob("dukascopy_xauusd_*_m5.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows[row["timestamp_utc"]] = CandleSnapshot(
                    timestamp_utc=datetime.fromisoformat(row["timestamp_utc"]),
                    open=float(row["open"]), high=float(row["high"]),
                    low=float(row["low"]), close=float(row["close"]),
                    volume=float(row.get("volume") or 0),
                )
    return sorted(rows.values(), key=lambda candle: candle.timestamp_utc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, action="append", choices=(365, 1095))
    args = parser.parse_args()
    settings = get_settings()
    bot = {item.id: item for item in load_bots_catalog(settings.bots_catalog_path)}[BOT_ID]
    candles = load_local_candles()
    if not candles:
        raise SystemExit("no local OHLC candles found")
    for days in args.days or [365, 1095]:
        replay = run_historical_replay(bot, candles, settings, days=days)
        save_local_backtest(settings.backtest_cache_path, replay, days)
        print(
            f"{BOT_ID} days={days} candles={replay.candles_evaluated} "
            f"candidates={replay.candidates_detected} eligible={replay.candidates_eligible} "
            f"trades={replay.summary.trades_count} net={replay.summary.net_pnl:.2f} "
            f"pf={replay.summary.profit_factor:.3f}"
        )


if __name__ == "__main__":
    main()
