"""Build V6.0's provisional replay by routing frozen V5 fills to V5.1/V5.2."""

from __future__ import annotations

from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse, TradeResult


ROOT = Path(__file__).resolve().parents[1]


def _key(trade: TradeResult) -> tuple[object, str]:
    return trade.opened_at_utc, trade.side.value


def main() -> None:
    source = HistoricalReplayResponse.model_validate_json(
        (ROOT / "data/backtests/core-zigzag-v5-365.json").read_text(encoding="utf-8")
    )
    v51 = HistoricalReplayResponse.model_validate_json(
        (ROOT / "data/backtests/core-zigzag-v7-365.json").read_text(encoding="utf-8")
    )
    v52 = HistoricalReplayResponse.model_validate_json(
        (ROOT / "data/backtests/core-zigzag-v9-365.json").read_text(encoding="utf-8")
    )
    v51_sells = {_key(trade): trade for trade in v51.trades if trade.side.value == "sell"}
    v52_buys = {_key(trade): trade for trade in v52.trades if trade.side.value == "buy"}
    kept: list[TradeResult] = []
    blocked = {"v60_v51_sell_context_block": 0, "v60_v52_buy_context_block": 0}

    for trade in source.trades:
        branch, selected = (
            ("v60_v52_buy_context", v52_buys.get(_key(trade)))
            if trade.side.value == "buy"
            else ("v60_v51_sell_context", v51_sells.get(_key(trade)))
        )
        if selected is None:
            blocked[f"{branch}_block"] += 1
            continue
        kept.append(selected.model_copy(update={
            "trade_id": selected.trade_id.replace("core-zigzag-v9", "core-zigzag-v10").replace("core-zigzag-v7", "core-zigzag-v10"),
            "setup": f"{selected.setup}; {branch}",
            "note": f"{selected.note} V6.0: ramo contextual selecionado={branch}.",
        }))

    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in kept], "v60-derived-v51-v52-context-router")
    expectancy, max_drawdown, max_loss_streak, total_costs = _risk_diagnostics(kept)
    output = source.model_copy(update={
        "bot_id": "core-zigzag-v10",
        "strategy_version": "2026-09-15-v60-v51-v52-context-router",
        "settings_fingerprint": "v60-provisional-derived-context-router",
        "candidates_detected": len(source.trades),
        "candidates_eligible": len(kept),
        "candidates_blocked": sum(blocked.values()),
        "blocked_reasons": blocked,
        "expectancy_r": expectancy,
        "max_drawdown_r": max_drawdown,
        "max_consecutive_losses": max_loss_streak,
        "total_costs": total_costs,
        "validation_status": "provisional_shadow",
        "validation_reason": "V6.0 routes frozen V5 fills to V5.1 sells and V5.2 buys; it requires a unified causal walk-forward replay.",
        "validation_folds": _validation_folds(kept, source.period_start_utc, source.period_end_utc, 30),
        "summary": snapshot.summary,
        "daily_pnl": snapshot.daily_pnl,
        "trades": kept,
        "assumptions": source.assumptions + [
            "V6.0 selects V5.2 for buys and V5.1 for sells; the alternate branch is not evaluated.",
            "This composition inherits frozen branch fills and exits and is not a unified causal execution replay.",
        ],
    })
    target = ROOT / "data/backtests/core-zigzag-v10-365.json"
    target.write_text(output.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{target}: {len(kept)} retained trades; {sum(blocked.values())} routed-context trades blocked")


if __name__ == "__main__":
    main()
