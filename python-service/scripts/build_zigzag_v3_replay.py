"""Build the causal V3 volatility-switch replay from the frozen V1/V2 results."""

from __future__ import annotations

import bisect
import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = 6.0


def metrics(rows: list[dict[str, object]]) -> dict[str, float | int]:
    pnl = [float(row["net_pnl_at_configured_volume"]) for row in rows]
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
        "net_pnl": round(sum(pnl), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else 0,
        "max_drawdown": round(drawdown, 2),
    }


def main() -> None:
    candles: dict[str, dict[str, str]] = {}
    for path in (ROOT / "data/research").glob("dukascopy_xauusd_*_m5.csv"):
        with path.open(encoding="utf-8", newline="") as handle:
            candles.update({row["timestamp_utc"]: row for row in csv.DictReader(handle)})
    ordered = sorted(
        (datetime.fromisoformat(timestamp), float(row["high"]) - float(row["low"]))
        for timestamp, row in candles.items()
    )
    candle_times = [item[0] for item in ordered]
    candle_ranges = [item[1] for item in ordered]

    def average_range(opened: datetime) -> float | None:
        index = bisect.bisect_left(candle_times, opened)
        values = candle_ranges[max(0, index - 60):index]
        return sum(values) / 60 if len(values) == 60 else None

    v1 = json.loads((ROOT / "data/backtests/core-zigzag-365.json").read_text(encoding="utf-8"))["trades"]
    v2: dict[tuple[str, str], dict[str, str]] = {}
    for filename in (
        "happy_gold_structural_tick_2025_selected.trades.csv",
        "happy_gold_structural_tick_2026_oos_selected.trades.csv",
        "happy_gold_structural_tick_2026_apr_aug_oos_selected.trades.csv",
    ):
        with (ROOT / "data/research/tick-backtests" / filename).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                v2[(row["opened_at_utc"], row["side"])] = row

    selected: list[dict[str, object]] = []
    for trade in v1:
        opened = datetime.fromisoformat(str(trade["opened_at_utc"]).replace("Z", "+00:00"))
        value = average_range(opened)
        if value is not None and value < THRESHOLD:
            selected.append({
                "opened_at_utc": trade["opened_at_utc"], "closed_at_utc": trade["closed_at_utc"],
                "side": trade["side"], "entry_price": trade["entry_price"], "exit_price": trade["exit_price"],
                "net_pnl_at_configured_volume": trade["net_pnl"], "volume_lots": .10,
                "risk_amount": 24.0, "stop_pips": 240.0, "mode": "v1_normal_volatility",
                "average_m5_range_60": round(value, 6),
            })
    for trade in v2.values():
        opened = datetime.fromisoformat(trade["opened_at_utc"])
        value = average_range(opened)
        if value is not None and value >= THRESHOLD:
            selected.append({
                "opened_at_utc": trade["opened_at_utc"], "closed_at_utc": trade["closed_at_utc"],
                "side": trade["side"], "entry_price": trade["entry_price"], "exit_price": trade["exit_price"],
                "net_pnl_at_configured_volume": round(float(trade["net_pnl"]) * 4, 6), "volume_lots": .40,
                "risk_amount": 24.0, "stop_pips": 60.0, "mode": "v2_structural_expansion",
                "average_m5_range_60": round(value, 6),
            })
    selected.sort(key=lambda row: str(row["opened_at_utc"]))
    output = ROOT / "data/research/tick-backtests/zigzag_scalper_v3_adaptive.trades.csv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    partitions = {
        "selection_2025_sep_dec": [row for row in selected if "2025-09" <= str(row["opened_at_utc"])[:7] <= "2025-12"],
        "holdout_2026_jan_apr": [row for row in selected if "2026-01" <= str(row["opened_at_utc"])[:7] <= "2026-04"],
        "fresh_holdout_2026_may_aug": [row for row in selected if "2026-05" <= str(row["opened_at_utc"])[:7] <= "2026-08"],
    }
    report = {"threshold": THRESHOLD, "feature": "mean range of previous 60 completed M5 candles", "overall": metrics(selected), "partitions": {name: metrics(rows) for name, rows in partitions.items()}}
    (ROOT / "data/research/zigzag_scalper_v3_adaptive.summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
