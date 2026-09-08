#!/usr/bin/env python3
"""Normalize cached replay trades to 1% equity risk without changing signals or exits."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.results_store import build_results_snapshot
from app.schemas import TradeResult


def normalize(payload: dict[str, object], risk_pct: float) -> dict[str, object]:
    source_assumptions = list(payload.get("assumptions", []))
    rows = list(payload.get("trades", []))
    events = []
    for row in rows:
        events.append((datetime.fromisoformat(str(row["opened_at_utc"]).replace("Z", "+00:00")), 0, row))
        events.append((datetime.fromisoformat(str(row["closed_at_utc"]).replace("Z", "+00:00")), 1, row))
    events.sort(key=lambda item: (item[0], item[1]))
    balance = 10_000.0
    risks: dict[str, float] = {}
    trades: list[TradeResult] = []
    for _, kind, row in events:
        key = str(row["trade_id"])
        if kind == 0:
            risks[key] = balance * risk_pct / 100
            continue
        risk = risks.pop(key)
        rr = float(row.get("rr_realized") or 0)
        pnl = round(risk * rr, 2)
        original_risk = float(row.get("risk_amount") or 0)
        scale = risk / original_risk if original_risk else 0
        fees = round(float(row.get("fees") or 0) * scale, 2)
        trade = TradeResult.model_validate({
            **row,
            "volume_lots": round(float(row["volume_lots"]) * scale, 4),
            "risk_amount": round(risk, 2),
            "gross_pnl": round(pnl + fees, 2),
            "fees": fees,
            "net_pnl": pnl,
            "note": f"Comparação normalizada; risco={risk_pct:g}% do patrimônio; {row.get('note', '')}",
        })
        trades.append(trade)
        balance += pnl
    trades.sort(key=lambda trade: trade.closed_at_utc or trade.opened_at_utc)
    results = build_results_snapshot([trade.model_dump(mode="json") for trade in trades], "normalized")
    start = datetime.fromisoformat(str(payload["period_start_utc"]).replace("Z", "+00:00"))
    end = datetime.fromisoformat(str(payload["period_end_utc"]).replace("Z", "+00:00"))
    expectancy, drawdown, loss_streak, costs = _risk_diagnostics(trades)
    payload.update({
        "strategy_version": f"normalized_{risk_pct:g}pct",
        "risk_per_trade_pct": risk_pct,
        "summary": results.summary.model_dump(mode="json"),
        "daily_pnl": [point.model_dump(mode="json") for point in results.daily_pnl],
        "trades": [trade.model_dump(mode="json") for trade in trades],
        "expectancy_r": expectancy,
        "max_drawdown_r": drawdown,
        "max_consecutive_losses": loss_streak,
        "total_costs": costs,
        "validation_folds": [fold.model_dump(mode="json") for fold in _validation_folds(trades, start, end, 30)],
        "assumptions": [
            "Comparação normalizada: cada entrada arrisca 1% do patrimônio disponível.",
            "Sinais, horários, stops, alvos e R realizado permanecem idênticos ao replay operacional de origem.",
            "Lote fixo e multiplicadores internos são ignorados somente nesta camada comparativa.",
            *source_assumptions,
        ],
    })
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/backtests-operational"))
    parser.add_argument("--target", type=Path, default=Path("data/backtests"))
    parser.add_argument("--risk-pct", type=float, default=1.0)
    parser.add_argument("--bot-id", action="append", help="Normalize only the selected bot id; repeat as needed.")
    args = parser.parse_args()
    args.target.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.source.glob("*-365.json")):
        source_payload = json.loads(path.read_text(encoding="utf-8"))
        if args.bot_id and source_payload.get("bot_id") not in set(args.bot_id):
            continue
        payload = normalize(source_payload, args.risk_pct)
        target = args.target / path.name
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        print(f"{payload['bot_id']}: {payload['summary']['net_pnl']:.2f}")


if __name__ == "__main__":
    main()
