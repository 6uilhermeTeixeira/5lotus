"""Evaluate the frozen Bot 21 range filter and a preregistered UTC session."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from validate_happy_gold_normalized_range_selector import load_candles, normalized_prior_range


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--candles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trades-output", type=Path)
    parser.add_argument("--bot21-trades-output", type=Path)
    parser.add_argument("--range-max", type=float, default=1.876955192)
    parser.add_argument("--session-start", type=int, default=3)
    parser.add_argument("--session-end", type=int, default=11)
    return parser.parse_args()


def metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    wins = [row for row in rows if float(row["net_pnl"]) > 0]
    losses = [row for row in rows if float(row["net_pnl"]) < 0]
    gross_profit = sum(float(row["net_pnl"]) for row in wins)
    gross_loss = -sum(float(row["net_pnl"]) for row in losses)
    equity = peak = drawdown = 0.0
    for row in sorted(rows, key=lambda item: str(item["opened_at_utc"])):
        equity += float(row["net_pnl"])
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "trades": len(rows), "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(rows), 3) if rows else None,
        "net_pnl": round(equity, 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(drawdown, 2),
    }


def main() -> None:
    args = parse_args()
    candle_times, candles = load_candles(args.candles)
    rows: list[dict[str, object]] = []
    with args.trades.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            opened = datetime.fromisoformat(row["opened_at_utc"])
            ratio = normalized_prior_range(opened, candle_times, candles)
            rows.append({**row, "opened": opened, "normalized_prior_m5_range": ratio})
    range_selected = [
        row for row in rows
        if row["normalized_prior_m5_range"] is not None
        and float(row["normalized_prior_m5_range"]) <= args.range_max
    ]
    session_selected = [
        row for row in range_selected
        if args.session_start <= row["opened"].hour < args.session_end  # type: ignore[union-attr]
    ]
    baseline = metrics(rows)
    bot21 = metrics(range_selected)
    session = metrics(session_selected)
    report = {
        "method": "Fresh 2026-04-15 through 2026-08-08 tick holdout with frozen filters and lifecycle.",
        "range_max": args.range_max,
        "session_utc": f"{args.session_start:02d}:00-{args.session_end:02d}:00",
        "bot19_structural_baseline": baseline,
        "bot21_normalized_range": bot21,
        "session_candidate": session,
        "decision": (
            "passed_fresh_holdout_candidate_for_shadow"
            if session["trades"] and float(session["profit_factor"] or 0) > float(bot21["profit_factor"] or 0)
            and float(session["max_drawdown"]) <= float(bot21["max_drawdown"])
            else "rejected_fresh_holdout"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.trades_output:
        args.trades_output.parent.mkdir(parents=True, exist_ok=True)
        excluded = {"opened", "normalized_prior_m5_range"}
        fields = [key for key in session_selected[0] if key not in excluded] if session_selected else ["opened_at_utc"]
        with args.trades_output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(session_selected)
    if args.bot21_trades_output:
        args.bot21_trades_output.parent.mkdir(parents=True, exist_ok=True)
        excluded = {"opened", "normalized_prior_m5_range"}
        fields = [key for key in range_selected[0] if key not in excluded] if range_selected else ["opened_at_utc"]
        with args.bot21_trades_output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(range_selected)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
