"""Evaluate a bounded ATR/R calibration matrix with a full-period confirmation."""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass

from app.backtest import run_historical_replay
from app.config import get_settings
from app.schemas import BotCatalogItem, HistoricalReplayResponse
from app.supabase_store import SupabaseStore


@dataclass(frozen=True)
class Candidate:
    name: str
    values: dict[str, float | int | str | bool]


COMMON = {"use_atr_geometry": True}
MATRICES = {
    "EURUSD": [
        Candidate("eur_08_15_4", {**COMMON, "atr_stop_multiplier": .8, "target_r": 1.5, "break_even_r": .75, "trailing_activation_r": 1.0, "trailing_distance_atr": .8, "max_holding_bars": 4, "pivot_span": 2, "session_start_utc": "06:00", "session_end_utc": "16:00"}),
        Candidate("eur_10_20_6", {**COMMON, "atr_stop_multiplier": 1.0, "target_r": 2.0, "break_even_r": .75, "trailing_activation_r": 1.0, "trailing_distance_atr": .8, "max_holding_bars": 6, "pivot_span": 2, "session_start_utc": "06:00", "session_end_utc": "17:00"}),
        Candidate("eur_12_20_8", {**COMMON, "atr_stop_multiplier": 1.2, "target_r": 2.0, "break_even_r": .75, "trailing_activation_r": 1.0, "trailing_distance_atr": .8, "max_holding_bars": 8, "pivot_span": 2, "session_start_utc": "06:00", "session_end_utc": "17:00"}),
        Candidate("eur_15_25_12", {**COMMON, "atr_stop_multiplier": 1.5, "target_r": 2.5, "break_even_r": 1.0, "trailing_activation_r": 1.2, "trailing_distance_atr": 1.0, "max_holding_bars": 12, "pivot_span": 2, "session_start_utc": "07:00", "session_end_utc": "17:00"}),
        Candidate("eur_10_15_span3", {**COMMON, "atr_stop_multiplier": 1.0, "target_r": 1.5, "break_even_r": .5, "trailing_activation_r": .8, "trailing_distance_atr": .6, "max_holding_bars": 4, "pivot_span": 3, "session_start_utc": "07:00", "session_end_utc": "16:00"}),
        Candidate("eur_12_25_span3", {**COMMON, "atr_stop_multiplier": 1.2, "target_r": 2.5, "break_even_r": 1.0, "trailing_activation_r": 1.5, "trailing_distance_atr": 1.0, "max_holding_bars": 8, "pivot_span": 3, "session_start_utc": "07:00", "session_end_utc": "18:00"}),
    ],
    "BTCUSD": [
        Candidate("btc_10_15_4", {**COMMON, "atr_stop_multiplier": 1.0, "target_r": 1.5, "break_even_r": .75, "trailing_activation_r": 1.0, "trailing_distance_atr": .8, "max_holding_bars": 4, "pivot_span": 2, "session_start_utc": "00:00", "session_end_utc": "23:59"}),
        Candidate("btc_12_20_6", {**COMMON, "atr_stop_multiplier": 1.2, "target_r": 2.0, "break_even_r": .75, "trailing_activation_r": 1.0, "trailing_distance_atr": .8, "max_holding_bars": 6, "pivot_span": 2, "session_start_utc": "00:00", "session_end_utc": "23:59"}),
        Candidate("btc_15_25_8", {**COMMON, "atr_stop_multiplier": 1.5, "target_r": 2.5, "break_even_r": 1.0, "trailing_activation_r": 1.2, "trailing_distance_atr": 1.0, "max_holding_bars": 8, "pivot_span": 2, "session_start_utc": "00:00", "session_end_utc": "23:59"}),
        Candidate("btc_20_30_12", {**COMMON, "atr_stop_multiplier": 2.0, "target_r": 3.0, "break_even_r": 1.0, "trailing_activation_r": 1.5, "trailing_distance_atr": 1.2, "max_holding_bars": 12, "pivot_span": 2, "session_start_utc": "00:00", "session_end_utc": "23:59"}),
        Candidate("btc_12_20_us", {**COMMON, "atr_stop_multiplier": 1.2, "target_r": 2.0, "break_even_r": .75, "trailing_activation_r": 1.0, "trailing_distance_atr": .8, "max_holding_bars": 6, "pivot_span": 3, "session_start_utc": "06:00", "session_end_utc": "22:00"}),
        Candidate("btc_15_25_late", {**COMMON, "atr_stop_multiplier": 1.5, "target_r": 2.5, "break_even_r": 1.0, "trailing_activation_r": 1.2, "trailing_distance_atr": 1.0, "max_holding_bars": 8, "pivot_span": 3, "session_start_utc": "12:00", "session_end_utc": "23:59"}),
    ],
}


def _score(replay: HistoricalReplayResponse) -> tuple[float, dict[str, float | int | str]]:
    populated = [fold for fold in replay.validation_folds if fold.trades_count > 0]
    positive_ratio = sum(fold.positive for fold in populated) / len(populated) if populated else 0.0
    score = positive_ratio * 2 + replay.expectancy_r + min(replay.summary.profit_factor, 2) - replay.max_drawdown_r / 100
    return score, {
        "trades": replay.summary.trades_count,
        "win_rate": replay.summary.win_rate_pct,
        "net_pnl": replay.summary.net_pnl,
        "profit_factor": replay.summary.profit_factor,
        "expectancy_r": replay.expectancy_r,
        "max_drawdown_r": replay.max_drawdown_r,
        "positive_fold_ratio": round(positive_ratio, 4),
        "validation": replay.validation_status,
    }


def _run(bot: BotCatalogItem, candles, settings, candidate: Candidate, days: int) -> tuple[Candidate, HistoricalReplayResponse, float, dict]:
    configured = deepcopy(settings)
    configured.happy_gold_market_calibrations = {bot.symbol.upper(): candidate.values}
    replay = run_historical_replay(bot, candles, configured, days=days)
    score, metrics = _score(replay)
    print(f"RESULT phase={days}d symbol={bot.symbol} candidate={candidate.name} score={score:.4f} metrics={metrics}", flush=True)
    return candidate, replay, score, metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", choices=sorted(MATRICES), required=True)
    parser.add_argument("--selection-days", type=int, default=180)
    args = parser.parse_args()
    bot_id = "bot-eur-13" if args.symbol == "EURUSD" else "bot-btc-13"
    source_id = "bot-eur-1" if args.symbol == "EURUSD" else bot_id
    settings = get_settings()
    store = SupabaseStore(settings)
    bot = next(bot for bot in store.list_bots() if bot.id == bot_id)
    all_candles = store.load_candles(bot, settings.backtest_candle_limit, source_bot_id=source_id)
    selection_bars = min(len(all_candles), max(4000, args.selection_days * 288 + 1000))
    selection_candles = all_candles[-selection_bars:]
    ranked = sorted(
        (_run(bot, selection_candles, settings, candidate, args.selection_days) for candidate in MATRICES[args.symbol]),
        key=lambda item: item[2],
        reverse=True,
    )
    print(f"SHORTLIST symbol={args.symbol} candidates={[item[0].name for item in ranked[:2]]}", flush=True)
    confirmations = [_run(bot, all_candles, settings, item[0], 365) for item in ranked[:2]]
    winner = max(confirmations, key=lambda item: item[2])
    candidate, replay, score, metrics = winner
    stable = (
        metrics["trades"] >= 100
        and metrics["profit_factor"] >= 1.15
        and metrics["expectancy_r"] > 0
        and metrics["positive_fold_ratio"] >= .6
    )
    print(f"WINNER symbol={args.symbol} candidate={candidate.name} stable={stable} score={score:.4f} values={candidate.values} metrics={metrics}", flush=True)


if __name__ == "__main__":
    main()
