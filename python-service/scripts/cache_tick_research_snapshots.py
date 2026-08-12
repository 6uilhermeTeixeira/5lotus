"""Publish dashboard snapshots from reproducible Dukascopy tick replays."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path

from app.backtest import replay_settings_fingerprint
from app.config import get_settings
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse, TradeResult
from app.supabase_store import SupabaseStore


ROOT = Path(__file__).resolve().parents[1]
SOURCES: dict[str, tuple[Path | tuple[Path, ...], float]] = {
    "bot-17": (ROOT / "data/research/tick-backtests/happy_gold_tick_impulse_2025_managed_60s_threshold50_spread10_cooldown9000_rearm0.5_context900s_1000.trades.csv", 240.0),
    "bot-18": (ROOT / "data/research/tick-backtests/happy_gold_zigzag_tick_context_2025_managed_stop60_hold60.trades.csv", 60.0),
    "bot-19": (ROOT / "data/research/tick-backtests/happy_gold_structural_tick_2025_selected.trades.csv", 60.0),
    "bot-21": ((
        ROOT / "data/research/tick-backtests/happy_gold_normalized_range_2025_2026_selected.trades.csv",
        ROOT / "data/research/tick-backtests/happy_gold_normalized_range_2026_apr_aug_selected.trades.csv",
    ), 60.0),
}


def load_trades(bot_id: str, source: Path | tuple[Path, ...], stop_pips: float) -> list[TradeResult]:
    trades: list[TradeResult] = []
    sources = source if isinstance(source, tuple) else (source,)
    for path in sources:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            side = row["side"]
            entry = float(row["entry_price"])
            exit_price = float(row["exit_price"])
            net_pnl = float(row["net_pnl"])
            risk_amount = stop_pips * 0.10
            direction = 1 if side == "buy" else -1
            trades.append(TradeResult(
                trade_id=f"tick-replay:{bot_id}:{len(trades) + 1}", symbol="XAUUSD", timeframe="TICK",
                setup=f"{bot_id}_dukascopy_tick_replay", side=side,
                opened_at_utc=datetime.fromisoformat(row["opened_at_utc"]),
                closed_at_utc=datetime.fromisoformat(row["closed_at_utc"]),
                volume_lots=0.10, entry_price=entry, exit_price=exit_price,
                stop_loss_price=entry - direction * stop_pips * 0.01,
                risk_amount=risk_amount, gross_pnl=net_pnl, net_pnl=net_pnl,
                rr_realized=net_pnl / risk_amount,
                note="Replay tick a tick Dukascopy; proxy da corretora não divulgada e sem execução real.",
            ))
    return trades


def max_drawdown_r(trades: list[TradeResult]) -> float:
    equity = peak = drawdown = 0.0
    for trade in trades:
        equity += float(trade.rr_realized or 0)
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return round(drawdown, 4)


def max_loss_streak(trades: list[TradeResult]) -> int:
    longest = current = 0
    for trade in trades:
        current = current + 1 if trade.net_pnl < 0 else 0
        longest = max(longest, current)
    return longest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, action="append", choices=(30, 120, 365))
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    days_list = args.days or [30, 120, 365]
    settings = get_settings()
    store = SupabaseStore(settings)
    bots = {bot.id: bot for bot in store.list_bots()}

    for bot_id, (source, stop_pips) in SOURCES.items():
        bot = bots[bot_id]
        all_trades = sorted(load_trades(bot_id, source, stop_pips), key=lambda trade: trade.opened_at_utc)
        period_end = max(trade.closed_at_utc for trade in all_trades if trade.closed_at_utc)
        source_start = all_trades[0].opened_at_utc
        for days in days_list:
            period_start = max(source_start, period_end - timedelta(days=days))
            trades = [trade for trade in all_trades if trade.opened_at_utc >= period_start]
            source_name = "+".join(path.name for path in source) if isinstance(source, tuple) else source.name
            snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in trades], f"dukascopy:{source_name}")
            rr_values = [float(trade.rr_realized or 0) for trade in trades]
            replay = HistoricalReplayResponse(
                bot_id=bot_id, symbol=bot.symbol, timeframe=bot.timeframe,
                risk_per_trade_pct=settings.backtest_risk_per_trade_pct,
                strategy_version="dukascopy-tick-replay-v2",
                settings_fingerprint=replay_settings_fingerprint(settings, bot),
                period_start_utc=period_start, period_end_utc=period_end,
                candles_evaluated=0, candidates_detected=len(trades), candidates_eligible=len(trades),
                expectancy_r=round(sum(rr_values) / len(rr_values), 4) if rr_values else 0,
                max_drawdown_r=max_drawdown_r(trades), max_consecutive_losses=max_loss_streak(trades),
                validation_status="promising_not_live" if bot_id in {"bot-19", "bot-21"} else "rejected_research",
                validation_reason=(
                    "walk_forward_candidate_requires_broker_tick_forward_validation"
                    if bot_id == "bot-21"
                    else "small_selected_sample_requires_forward_validation"
                    if bot_id == "bot-19"
                    else "annual_tick_replay_did_not_pass_selection_gate"
                ),
                assumptions=[
                    "Dukascopy XAUUSD substitui a corretora não divulgada do forward test original.",
                    "Entradas e saídas usam preços executáveis Bid/Ask com spread modelado de 10 pips.",
                    "Replay de pesquisa em lote fixo 0,10; nenhuma ordem foi enviada ao mercado.",
                ],
                summary=snapshot.summary, daily_pnl=snapshot.daily_pnl, trades=trades,
            )
            if args.publish:
                store.save_backtest_snapshot(replay, days)
            print(f"{bot_id} days={days} trades={len(trades)} net={snapshot.summary.net_pnl:.2f} published={args.publish}")


if __name__ == "__main__":
    main()
