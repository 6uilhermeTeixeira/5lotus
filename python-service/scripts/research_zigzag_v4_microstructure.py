"""Walk-forward research for ZigZag V4 using causal one-second features and exits."""

from __future__ import annotations

import bisect
import csv
from datetime import UTC, datetime, time, timedelta
from itertools import product
import json
from pathlib import Path

import duckdb

from app.config import get_settings
from app.history_sync import load_m5_candles, load_tick_indicators
from app.local_dataset import DatasetRelease
from app.schemas import AccountSnapshot, DecisionRequest
from app.strategy import _happy_gold_zigzag_setup


ROOT = Path(__file__).resolve().parents[1]
PIP_SIZE = 0.01
LOT = 0.20
STOP_PIPS = 240.0
TARGET_PIPS = 1000.0
MAX_HOLD_SECONDS = 60
COMMISSION_PER_LOT = 4.5


def metrics(rows: list[dict[str, object]]) -> dict[str, float | int | None]:
    pnl = [float(row["net_pnl"]) for row in rows]
    gross_profit = sum(value for value in pnl if value > 0)
    gross_loss = -sum(value for value in pnl if value < 0)
    equity = peak = drawdown = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "trades": len(rows),
        "wins": sum(value > 0 for value in pnl),
        "win_rate_pct": round(100 * sum(value > 0 for value in pnl) / len(pnl), 3) if pnl else None,
        "net_pnl": round(sum(pnl), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(drawdown, 2),
    }


def partition(rows: list[dict[str, object]], start: str, end: str) -> list[dict[str, object]]:
    return [row for row in rows if start <= str(row["opened_at_utc"])[:10] <= end]


def build_signals(candles: list, indicators: dict[int, dict[str, float]]) -> list[dict[str, object]]:
    output = []
    for index in range(60, len(candles)):
        candle = candles[index]
        opened = candle.timestamp_utc + timedelta(minutes=5)
        if not time(3) <= opened.time() < time(19):
            continue
        item = indicators.get(int(opened.timestamp() * 1000), {})
        request = DecisionRequest(
            bot_id="core-zigzag-v4",
            request_id=f"v4-{int(opened.timestamp())}",
            timestamp_utc=opened,
            symbol="XAUUSD",
            timeframe="M5",
            bid=candle.close,
            ask=candle.close,
            spread_points=0,
            point_size=PIP_SIZE,
            value_per_point_per_lot=1,
            candles=candles[index - 60:index + 1],
            positions=[],
            account=AccountSnapshot(balance=10_000, equity=10_000, margin_free=10_000),
            indicators=item,
        )
        setup = _happy_gold_zigzag_setup(request)
        if setup is None:
            continue
        direction = 1 if setup.action.value == "buy" else -1
        output.append({
            "opened_at_utc": opened.isoformat(),
            "side": setup.action.value,
            "direction": direction,
            "move_5s": direction * item.get("impulse_5s_move_points", 0),
            "move_30s": direction * item.get("impulse_30s_move_points", 0),
            "move_60s": direction * item.get("impulse_60s_move_points", 0),
            "efficiency": item.get("micro_30s_efficiency", 0),
            "acceleration": item.get("micro_tick_acceleration_5s_vs_10s", 0),
            "spread_pips": item.get("micro_5s_mean_spread_pips", 0),
        })
    return output


def load_day_quotes(release: DatasetRelease, day: str) -> tuple[list[int], list[float], list[float]]:
    manifest_row = next(row for row in release.manifest["aggregations"]["1s"] if row["day"] == day)
    connection = duckdb.connect(":memory:")
    try:
        values = connection.execute(
            "SELECT t,c,spread_mean FROM read_parquet(?) ORDER BY t",
            [[str(release.root / manifest_row["path"])]],
        ).fetchall()
    finally:
        connection.close()
    return (
        [int(row[0]) for row in values],
        [float(row[1]) - float(row[2]) / 2 for row in values],
        [float(row[1]) + float(row[2]) / 2 for row in values],
    )


def simulate(signal: dict[str, object], quotes: tuple[list[int], list[float], list[float]]) -> dict[str, object]:
    timestamps, bids, asks = quotes
    opened = datetime.fromisoformat(str(signal["opened_at_utc"]))
    opened_msc = int(opened.timestamp() * 1000)
    left = bisect.bisect_left(timestamps, opened_msc)
    right = bisect.bisect_right(timestamps, opened_msc + MAX_HOLD_SECONDS * 1000)
    side = str(signal["side"])
    direction = int(signal["direction"])
    entry = asks[left] if side == "buy" else bids[left]
    stop = entry - direction * STOP_PIPS * PIP_SIZE
    target = entry + direction * TARGET_PIPS * PIP_SIZE
    exit_index = max(left, right - 1)
    exit_price = bids[exit_index] if side == "buy" else asks[exit_index]
    reason = "time_60s"
    for index in range(left, right):
        executable = bids[index] if side == "buy" else asks[index]
        if direction * (executable - stop) <= 0:
            exit_index, exit_price, reason = index, executable, "stop"
            break
        if direction * (executable - target) >= 0:
            exit_index, exit_price, reason = index, executable, "target"
            break
    pnl_pips = direction * (exit_price - entry) / PIP_SIZE
    return {
        **signal,
        "closed_at_utc": datetime.fromtimestamp(timestamps[exit_index] / 1000, UTC).isoformat(),
        "entry_price": round(entry, 6),
        "exit_price": round(exit_price, 6),
        "exit_reason": reason,
        "duration_seconds": round((timestamps[exit_index] - opened_msc) / 1000, 3),
        "pnl_pips": round(pnl_pips, 3),
        "net_pnl": round(pnl_pips * LOT - COMMISSION_PER_LOT * LOT, 2),
    }


def main() -> None:
    settings = get_settings()
    release = DatasetRelease.open(settings.lotus_data_root, "CURRENT")
    candles = load_m5_candles(release, "XAUUSD", 365)
    indicators = load_tick_indicators(release, "XAUUSD", candles)
    base_signals = build_signals(candles, indicators)
    days = sorted({str(row["opened_at_utc"])[:10] for row in base_signals})
    quotes = {day: load_day_quotes(release, day) for day in days}
    candidates = []
    for move_5s, move_30s, move_60s, efficiency, acceleration in product(
        (10.0, 20.0), (50.0, 75.0), (100.0, 120.0), (.12, .18), (.8, 1.0)
    ):
        filtered = [
            row for row in base_signals
            if float(row["move_5s"]) >= move_5s
            and float(row["move_30s"]) >= move_30s
            and float(row["move_60s"]) >= move_60s
            and float(row["move_5s"]) <= float(row["move_30s"]) <= float(row["move_60s"])
            and float(row["efficiency"]) >= efficiency
            and float(row["acceleration"]) >= acceleration
            and float(row["spread_pips"]) <= 100
        ]
        trades = [simulate(row, quotes[str(row["opened_at_utc"])[:10]]) for row in filtered]
        candidates.append({
            "parameters": {
                "min_5s_move_pips": move_5s,
                "min_30s_move_pips": move_30s,
                "min_60s_move_pips": move_60s,
                "min_efficiency": efficiency,
                "min_tick_acceleration": acceleration,
            },
            "training_2025_sep_dec": metrics(partition(trades, "2025-09-01", "2025-12-31")),
            "trades": trades,
        })
    eligible = [
        row for row in candidates
        if int(row["training_2025_sep_dec"]["trades"]) >= 20
        and float(row["training_2025_sep_dec"]["profit_factor"] or 0) >= 1.15
    ]
    ranked = sorted(
        eligible or candidates,
        key=lambda row: (
            float(row["training_2025_sep_dec"]["profit_factor"] or 0),
            float(row["training_2025_sep_dec"]["net_pnl"]),
        ),
        reverse=True,
    )
    selected = ranked[0]
    selected_trades = selected["trades"]
    report = {
        "method": "Entry thresholds selected on Sep-Dec 2025; frozen on two 2026 holdouts.",
        "dataset_version": release.version,
        "base_zigzag_signals": len(base_signals),
        "selection_gate": "at least 20 training trades and PF >= 1.15",
        "decision": "candidate" if eligible else "rejected_no_training_configuration_passed",
        "execution_model": {
            "resolution": "1s", "stop_pips": STOP_PIPS, "target_pips": TARGET_PIPS,
            "max_hold_seconds": MAX_HOLD_SECONDS, "lot": LOT, "commission_per_lot": COMMISSION_PER_LOT,
        },
        "selected": {
            "parameters": selected["parameters"],
            "training_2025_sep_dec": selected["training_2025_sep_dec"],
            "holdout_2026_jan_apr": metrics(partition(selected_trades, "2026-01-01", "2026-04-30")),
            "fresh_holdout_2026_may_aug": metrics(partition(selected_trades, "2026-05-01", "2026-08-31")),
            "overall": metrics(selected_trades),
        },
        "top_training_candidates": [
            {"parameters": row["parameters"], "training_2025_sep_dec": row["training_2025_sep_dec"]}
            for row in ranked[:10]
        ],
        "limitations": [
            "One-second OHLC cannot resolve ordering inside the second.",
            "Dukascopy spread may differ from the original broker.",
            "Original entry history contains positive cases but no rejected-signal controls.",
        ],
    }
    (ROOT / "data/research/zigzag_scalper_v4_microstructure.walkforward.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    with (ROOT / "data/research/tick-backtests/zigzag_scalper_v4_microstructure.trades.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected_trades[0]))
        writer.writeheader()
        writer.writerows(selected_trades)
    print(json.dumps(report["selected"], indent=2))


if __name__ == "__main__":
    main()
