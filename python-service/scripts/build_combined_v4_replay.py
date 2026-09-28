"""Build the provisional parallel replay for Combined Portfolio V4."""
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse

ROOT = Path(__file__).resolve().parents[1]


def main():
    sources = [
        ("core-zigzag-v10-365.json", "zigzag-v4.0"),
        ("core-zigzag-v8-365.json", "zigzag-v5.1"),
        ("core-stochastic-v4-365.json", "stochastic-v4"),
    ]
    replays = [
        (HistoricalReplayResponse.model_validate_json((ROOT / "data/backtests" / filename).read_text()), component)
        for filename, component in sources
    ]
    trades = []
    for replay, component in replays:
        trades.extend(trade.model_copy(update={
            "trade_id": trade.trade_id.replace(replay.bot_id, "core-combined-v4"),
            "setup": f"{trade.setup}; portfolio_component={component}",
        }) for trade in replay.trades)
    trades.sort(key=lambda trade: (trade.opened_at_utc, trade.trade_id))
    reference = replays[0][0]
    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in trades], "combined-v4-provisional-parallel")
    expectancy, drawdown, streak, costs = _risk_diagnostics(trades)
    output = reference.model_copy(update={
        "bot_id": "core-combined-v4",
        "strategy_version": "2026-09-15-combined-v4-parallel",
        "settings_fingerprint": "combined-v4-provisional-union",
        "candidates_detected": len(trades),
        "candidates_eligible": len(trades),
        "candidates_blocked": 0,
        "blocked_reasons": {},
        "expectancy_r": expectancy,
        "max_drawdown_r": drawdown,
        "max_consecutive_losses": streak,
        "total_costs": costs,
        "validation_status": "provisional_shadow",
        "validation_reason": "Parallel union of frozen V4.0, V5.1 and Stochastic V4 fills; simultaneous entries are intentionally preserved.",
        "validation_folds": _validation_folds(trades, reference.period_start_utc, reference.period_end_utc, 30),
        "summary": snapshot.summary,
        "daily_pnl": snapshot.daily_pnl,
        "trades": trades,
        "assumptions": reference.assumptions + ["Combined V4 preserves duplicate V4.0/V5.1 entries and has no unified causal portfolio execution replay."],
    })
    target = ROOT / "data/backtests/core-combined-v4-365.json"
    target.write_text(output.model_dump_json(indent=2) + "\n")
    print(f"{target}: {len(trades)} parallel trades")


if __name__ == "__main__":
    main()
