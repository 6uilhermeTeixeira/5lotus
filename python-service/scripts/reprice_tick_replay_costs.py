#!/usr/bin/env python3
"""Reprice a fixed-spread tick replay while preserving its frozen lifecycle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds, replay_settings_fingerprint
from app.config import get_settings
from app.results_store import build_results_snapshot, load_bots_catalog
from app.schemas import TradeResult


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-spread-pips", type=float, required=True)
    parser.add_argument("--target-spread-pips", type=float, default=0)
    parser.add_argument("--commission-per-lot", type=float, default=4.50)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    settings = get_settings()
    bot = next(bot for bot in load_bots_catalog(settings.bots_catalog_path) if bot.id == payload["bot_id"])
    spread_delta = args.source_spread_pips - args.target_spread_pips
    half_price_delta = spread_delta * settings.backtest_point_size / 2
    trades: list[TradeResult] = []
    for raw in payload["trades"]:
        direction = 1 if raw["side"] == "buy" else -1
        volume = float(raw["volume_lots"])
        gross = float(raw["net_pnl"]) + spread_delta * settings.backtest_value_per_point_per_lot * volume
        fees = args.commission_per_lot * volume
        net = gross - fees
        risk = float(raw.get("risk_amount") or 0)
        trades.append(TradeResult.model_validate({
            **raw,
            "entry_price": float(raw["entry_price"]) - direction * half_price_delta,
            "exit_price": float(raw["exit_price"]) + direction * half_price_delta,
            "stop_loss_price": float(raw["stop_loss_price"]) - direction * half_price_delta if raw.get("stop_loss_price") is not None else None,
            "gross_pnl": round(gross, 2),
            "fees": round(fees, 2),
            "net_pnl": round(net, 2),
            "rr_realized": net / risk if risk else 0,
            "note": (
                f"Reprecificação contrafactual: spread {args.source_spread_pips:g}->{args.target_spread_pips:g} pips; "
                f"comissão round-turn US$ {args.commission_per_lot:g}/lote; sinais e timestamps congelados."
            ),
        }))
    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in trades], "repriced-tick-replay")
    start = datetime.fromisoformat(str(payload["period_start_utc"]).replace("Z", "+00:00"))
    end = datetime.fromisoformat(str(payload["period_end_utc"]).replace("Z", "+00:00"))
    expectancy, drawdown, loss_streak, costs = _risk_diagnostics(trades)
    settings.backtest_spread_points = args.target_spread_pips
    settings.backtest_commission_per_lot = args.commission_per_lot
    payload.update({
        "strategy_version": f"repriced_zero_spread_commission_{args.commission_per_lot:g}",
        "settings_fingerprint": replay_settings_fingerprint(settings, bot),
        "summary": snapshot.summary.model_dump(mode="json"),
        "daily_pnl": [point.model_dump(mode="json") for point in snapshot.daily_pnl],
        "trades": [trade.model_dump(mode="json") for trade in trades],
        "expectancy_r": expectancy,
        "max_drawdown_r": drawdown,
        "max_consecutive_losses": loss_streak,
        "total_costs": costs,
        "validation_folds": [fold.model_dump(mode="json") for fold in _validation_folds(trades, start, end, 30)],
        "assumptions": [
            "Dukascopy XAUUSD substitui a corretora Fusion Markets; validação forward continua obrigatória.",
            f"Spread contrafactual de {args.target_spread_pips:g} pips e comissão round-turn de US$ {args.commission_per_lot:g} por lote.",
            "Sinais, sequência e timestamps de saída foram congelados a partir do replay de 10 pips; mudanças intratick em stops, trailing ou gatilhos não são reconstruídas.",
        ],
    })
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"bot_id": payload["bot_id"], "summary": payload["summary"], "total_costs": costs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
