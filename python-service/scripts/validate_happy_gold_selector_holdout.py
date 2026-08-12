from __future__ import annotations

import argparse
import bisect
import csv
import json
from datetime import datetime
from pathlib import Path


PIP_SIZE = 0.01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate fixed selector rules outside the labeled period.")
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--candles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--labeled-start", default="2025-10-15T01:02:34.271000+00:00")
    return parser.parse_args()


def ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    wins = [row for row in rows if float(row["net_pnl"]) > 0]
    losses = [row for row in rows if float(row["net_pnl"]) < 0]
    gross_profit = sum(float(row["net_pnl"]) for row in wins)
    gross_loss = -sum(float(row["net_pnl"]) for row in losses)
    return {
        "trades": len(rows), "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(rows), 3) if rows else None,
        "net_pnl": round(sum(float(row["net_pnl"]) for row in rows), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
    }


def main() -> None:
    args = parse_args()
    with args.signals.open(encoding="utf-8", newline="") as handle:
        signals = list(csv.DictReader(handle))
    candle_times: list[datetime] = []
    closes: list[float] = []
    with args.candles.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            candle_times.append(datetime.fromisoformat(row["timestamp_utc"]))
            closes.append(float(row["close"]))

    enriched: list[dict[str, object]] = []
    for signal in signals:
        opened = datetime.fromisoformat(signal["opened_at_utc"])
        bucket = opened.replace(minute=opened.minute // 5 * 5, second=0, microsecond=0)
        index = bisect.bisect_left(candle_times, bucket)
        history = closes[max(0, index - 30):index]
        direction = 1 if signal["side"] == "buy" else -1
        ema20 = ema(history[-20:], 20)
        extension = direction * (float(signal["entry_price"]) - float(signal["pivot"])) / PIP_SIZE
        enriched.append({
            **signal,
            "opened": opened,
            "weekday": opened.weekday(),
            "ema20_gap": direction * (history[-1] - ema20) / PIP_SIZE,
            "extension": extension,
            "context": float(signal["context_move_pips"]),
        })

    rules = {
        "baseline": lambda row: True,
        "balanced": lambda row: row["weekday"] != 4 and float(row["ema20_gap"]) >= 500 and float(row["extension"]) <= 50,
        "balanced_context_1000": lambda row: row["weekday"] != 4 and float(row["ema20_gap"]) >= 500 and float(row["context"]) >= 1000 and float(row["extension"]) <= 50,
        "strict": lambda row: row["weekday"] != 4 and float(row["ema20_gap"]) >= 900 and float(row["context"]) >= 1000 and float(row["extension"]) <= 50,
    }
    labeled_start = datetime.fromisoformat(args.labeled_start)
    report: dict[str, object] = {
        "method": "Fixed selector rules derived from entry matching, financially evaluated before the labeled period.",
        "replay_geometry": "modeled spread 10 pips; fixed stop 60 pips; maximum hold 30 seconds",
        "holdout_period": f"{min(row['opened'] for row in enriched).isoformat()} to {labeled_start.isoformat()}",
        "rules": {},
        "caution": "The holdout predates the labeled period; it tests temporal portability but is not a future walk-forward test.",
    }
    rule_report = report["rules"]
    assert isinstance(rule_report, dict)
    for name, rule in rules.items():
        selected = [row for row in enriched if rule(row)]
        rule_report[name] = {
            "holdout_jan_to_pre_label": metrics([row for row in selected if row["opened"] < labeled_start]),
            "labeled_period": metrics([row for row in selected if row["opened"] >= labeled_start]),
            "full_year": metrics(selected),
        }
    strict_timestamps = {
        str(row["opened_at_utc"]) for row in enriched if rules["strict"](row)
    }
    robustness: dict[str, object] = {}
    pattern = "happy_gold_zigzag_tick_context_2025_*.trades.csv"
    for path in sorted(args.signals.parent.glob(pattern)):
        with path.open(encoding="utf-8", newline="") as handle:
            selected = [
                row for row in csv.DictReader(handle)
                if row["opened_at_utc"] in strict_timestamps
            ]
        scenario = path.stem.removeprefix("happy_gold_zigzag_tick_context_2025_")
        robustness[scenario] = metrics(selected)
    report["strict_rule_management_robustness"] = robustness
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
