#!/usr/bin/env python3
"""Walk-forward search for an isolated shadow Multitimeframe Trend V2."""

from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ProcessPoolExecutor
from copy import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

from app.backtest import run_historical_replay
from app.config import get_settings
from app.schemas import BotCatalogItem, CandleSnapshot


_CANDLES: list[CandleSnapshot] = []


@dataclass(frozen=True)
class Variant:
    strength_min: float
    session_start_hour: int
    session_end_hour: int
    stop_atr: float = 1.2
    target_rr: float = .75
    max_holding_bars: int = 12


def load_candles(path: Path) -> list[CandleSnapshot]:
    candles = []
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            candles.append(CandleSnapshot(
                timestamp_utc=datetime.fromtimestamp(int(row["timestamp"]) / 1000, timezone.utc),
                open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                close=float(row["close"]), volume=float(row["volume"]),
            ))
    return candles


def evaluate_shared(args: tuple[Variant, int]) -> dict[str, object]:
    variant, days = args
    settings = copy(get_settings())
    for key, value in asdict(variant).items():
        setattr(settings, f"multitimeframe_v2_{key}", value)
    bot = BotCatalogItem(
        id="research-multitimeframe-v2", name="Multitimeframe V2", description="",
        strategy_profile="multitimeframe_trend_pullback_v2_shadow", symbol="XAUUSD", timeframe="M5",
    )
    replay = run_historical_replay(bot, _CANDLES, settings, days=days)
    folds = [fold for fold in replay.validation_folds if fold.trades_count]
    split = replay.period_start_utc + (replay.period_end_utc - replay.period_start_utc) * .7
    train = [fold for fold in folds if fold.period_end_utc <= split]
    holdout = [fold for fold in folds if fold.period_start_utc >= split]
    summary = replay.summary
    return {
        **asdict(variant), "trades": summary.trades_count, "net_pnl": summary.net_pnl,
        "profit_factor": summary.profit_factor, "win_rate_pct": summary.win_rate_pct,
        "expectancy_r": replay.expectancy_r, "max_drawdown_r": replay.max_drawdown_r,
        "positive_folds": sum(fold.positive for fold in folds), "populated_folds": len(folds),
        "train_net_pnl": round(sum(fold.net_pnl for fold in train), 2),
        "holdout_net_pnl": round(sum(fold.net_pnl for fold in holdout), 2),
        "holdout_positive_folds": sum(fold.positive for fold in holdout), "holdout_folds": len(holdout),
        "validation_status": replay.validation_status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candles", type=Path, default=Path("/home/codexops/lotus-data/derived/xauusd-m5-current.csv"))
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--output", type=Path, default=Path("data/research/multitimeframe_v2_signal_grid.json"))
    args = parser.parse_args()
    global _CANDLES
    _CANDLES = load_candles(args.candles)
    variants = [Variant(*values) for values in product((.5, .7, .9, 1.1), (10, 12, 13), (15, 16, 18))]
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(evaluate_shared, ((variant, args.days) for variant in variants)))
    results.sort(key=lambda row: (row["holdout_net_pnl"], row["profit_factor"]), reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"variants_tested": len(results), "results": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results[:10], indent=2))


if __name__ == "__main__":
    main()
