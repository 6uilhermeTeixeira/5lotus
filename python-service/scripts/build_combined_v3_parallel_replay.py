#!/usr/bin/env python3
"""Build the parallel three-V3 shadow portfolio with 1% risk per component trade."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds, replay_settings_fingerprint
from app.config import get_settings
from app.results_store import build_results_snapshot
from app.schemas import BotCatalogItem, TradeResult


ROOT = Path(__file__).resolve().parents[1]
INITIAL_BALANCE = 10_000.0
RISK_FRACTION = .01


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365, choices=(365, 1095))
    args = parser.parse_args()
    sources = {
        "zigzag-v3": ROOT / f"data/backtests/core-zigzag-v3-{args.days}.json",
        "stochastic-v3": ROOT / f"data/backtests/core-stochastic-v3-{args.days}.json",
        "multitimeframe-v3": ROOT / f"data/backtests/core-multitimeframe-v3-{args.days}.json",
    }
    output = ROOT / f"data/backtests/core-combined-v3-{args.days}.json"
    source_payloads = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in sources.items()}
    template = deepcopy(next(iter(source_payloads.values())))
    events: list[tuple[datetime, int, str, dict[str, object]]] = []
    for component, payload in source_payloads.items():
        for row in payload["trades"]:
            events.append((datetime.fromisoformat(str(row["opened_at_utc"]).replace("Z", "+00:00")), 0, component, row))
            events.append((datetime.fromisoformat(str(row["closed_at_utc"]).replace("Z", "+00:00")), 1, component, row))
    events.sort(key=lambda item: (item[0], item[1]))

    balance = INITIAL_BALANCE
    open_risk: dict[str, float] = {}
    completed: list[TradeResult] = []
    for _, event_type, component, row in events:
        source_id = str(row["trade_id"])
        key = f"{component}:{source_id}"
        if event_type == 0:
            open_risk[key] = balance * RISK_FRACTION
            continue
        risk = open_risk.pop(key)
        rr = float(row.get("rr_realized") or 0)
        pnl = round(risk * rr, 2)
        original_risk = float(row.get("risk_amount") or 0)
        scale = risk / original_risk if original_risk else 0
        fees = round(float(row.get("fees") or 0) * scale, 2)
        trade = TradeResult.model_validate({
            **row,
            "trade_id": f"parallel:{component}:{source_id}",
            "setup": f"{component}_parallel",
            "volume_lots": round(float(row["volume_lots"]) * scale, 4),
            "risk_amount": round(risk, 2),
            "gross_pnl": round(pnl + fees, 2),
            "fees": fees,
            "net_pnl": pnl,
            "note": f"Portfólio paralelo; componente={component}; risco=1%; {row.get('note', '')}",
        })
        completed.append(trade)
        balance += pnl

    completed.sort(key=lambda trade: trade.closed_at_utc or trade.opened_at_utc)
    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in completed], "parallel-v3")
    period_start = min(datetime.fromisoformat(str(payload["period_start_utc"]).replace("Z", "+00:00")) for payload in source_payloads.values())
    period_end = max(datetime.fromisoformat(str(payload["period_end_utc"]).replace("Z", "+00:00")) for payload in source_payloads.values())
    expectancy, drawdown, max_losses, total_costs = _risk_diagnostics(completed)
    folds = _validation_folds(completed, period_start, period_end, 30)
    template.update({
        "bot_id": "core-combined-v3",
        "strategy_version": "portfolio_v3_parallel_1pct",
        "period_start_utc": period_start.isoformat().replace("+00:00", "Z"),
        "period_end_utc": period_end.isoformat().replace("+00:00", "Z"),
        "risk_per_trade_pct": 1.0,
        "settings_fingerprint": replay_settings_fingerprint(
            get_settings(),
            BotCatalogItem(
                id="core-combined-v3", name="Combinação V3", description="",
                strategy_profile="portfolio_v3_adaptive_union_shadow", symbol="XAUUSD", timeframe="M5",
            ),
        ),
        "summary": snapshot.summary.model_dump(mode="json"),
        "daily_pnl": [point.model_dump(mode="json") for point in snapshot.daily_pnl],
        "trades": [trade.model_dump(mode="json") for trade in completed],
        "expectancy_r": expectancy,
        "max_drawdown_r": drawdown,
        "max_consecutive_losses": max_losses,
        "total_costs": total_costs,
        "validation_folds": [fold.model_dump(mode="json") for fold in folds],
        "validation_status": "promising_not_live",
        "validation_reason": "parallel_1pct_per_component_requires_forward_validation",
        "candidates_detected": len(completed),
        "candidates_eligible": len(completed),
        "candidates_blocked": 0,
        "blocked_reasons": {},
        "assumptions": [
            "As três V3 mantêm posições, cooldowns e trilhas independentes.",
            "Custos dos componentes preservam spread de 0 pontos, slippage configurada e comissão round-turn de US$ 4,50 por lote da conta Fusion Zero.",
            "Cada entrada arrisca 1% do patrimônio observado no instante da abertura; exposição simultânea máxima teórica de 3%.",
            "Compras e vendas simultâneas são permitidas em shadow; nenhuma oportunidade é removida por conflito entre componentes.",
            "A trilha ZigZag preserva o replay específico disponível, mas ainda requer validação forward com ticks da corretora.",
        ],
    })
    output.write_text(json.dumps(template, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "trades": len(completed), "ending_balance": round(balance, 2),
        "net_pnl": snapshot.summary.net_pnl, "profit_factor": snapshot.summary.profit_factor,
        "expectancy_r": expectancy, "max_drawdown_r": drawdown,
        "positive_folds": sum(fold.positive for fold in folds), "folds": len(folds),
    }, indent=2))


if __name__ == "__main__":
    main()
