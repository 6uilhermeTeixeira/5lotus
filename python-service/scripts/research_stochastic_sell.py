#!/usr/bin/env python3
"""Walk-forward parameter research for the shadow-only Stochastic Sell strategy."""

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
    threshold: float
    target_rr: float
    partial_pct: float
    cutoff_hour: int
    regime_enabled: bool = True


def load_candles(path: Path) -> list[CandleSnapshot]:
    candles: list[CandleSnapshot] = []
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            candles.append(CandleSnapshot(
                timestamp_utc=datetime.fromtimestamp(int(row["timestamp"]) / 1000, timezone.utc),
                open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                close=float(row["close"]), volume=float(row["volume"]),
            ))
    return candles


def evaluate(candles: list[CandleSnapshot], variant: Variant, days: int) -> dict[str, object]:
    settings = copy(get_settings())
    settings.backtest_regime_enabled = variant.regime_enabled
    settings.stochastic_sell_v2_threshold = variant.threshold
    settings.stochastic_sell_v2_target_rr = variant.target_rr
    settings.stochastic_sell_v2_partial_pct = variant.partial_pct
    settings.stochastic_sell_v2_cutoff_hour = variant.cutoff_hour
    bot = BotCatalogItem(
        id="research-stochastic", name="Stochastic research", description="",
        strategy_profile="stochastic_sell_v2_shadow", symbol="XAUUSD", timeframe="M5",
    )
    replay = run_historical_replay(bot, candles, settings, days=days)
    folds = [fold for fold in replay.validation_folds if fold.trades_count]
    summary = replay.summary
    split = replay.period_start_utc + (replay.period_end_utc - replay.period_start_utc) * 0.7
    train = [fold for fold in folds if fold.period_end_utc <= split]
    holdout = [fold for fold in folds if fold.period_start_utc >= split]
    return {
        **asdict(variant), "trades": summary.trades_count, "net_pnl": summary.net_pnl,
        "profit_factor": summary.profit_factor, "win_rate_pct": summary.win_rate_pct,
        "expectancy_r": replay.expectancy_r, "max_drawdown_r": replay.max_drawdown_r,
        "positive_folds": sum(fold.positive for fold in folds), "populated_folds": len(folds),
        "train_net_pnl": round(sum(fold.net_pnl for fold in train), 2),
        "holdout_net_pnl": round(sum(fold.net_pnl for fold in holdout), 2),
        "holdout_positive_folds": sum(fold.positive for fold in holdout),
        "holdout_folds": len(holdout), "validation_status": replay.validation_status,
    }


def evaluate_shared(args: tuple[Variant, int]) -> dict[str, object]:
    variant, days = args
    return evaluate(_CANDLES, variant, days)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candles", type=Path, default=Path("/home/codexops/lotus-data/derived/xauusd-m5-current.csv"))
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--output", type=Path, default=Path("data/research/stochastic_sell_grid.json"))
    args = parser.parse_args()
    global _CANDLES
    _CANDLES = load_candles(args.candles)
    variants = [Variant(*values) for values in product(
        (55.0, 65.0, 75.0, 85.0), (1.5, 2.0, 2.5), (50.0,), (14, 16, 18),
    )]
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(evaluate_shared, ((variant, args.days) for variant in variants)))
    results.sort(key=lambda row: (row["holdout_net_pnl"], row["profit_factor"]), reverse=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.candles), "days": args.days,
        "method": "70/30 chronological split approximated with complete 30-day validation folds",
        "variants_tested": len(results), "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(results[:10], indent=2))


if __name__ == "__main__":
    main()
