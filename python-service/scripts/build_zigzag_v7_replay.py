"""Exploratory intersection; retained V5 fills are not a fresh execution replay."""
from bisect import bisect_right
from datetime import timedelta
from pathlib import Path
from app.backtest import _risk_diagnostics, _validation_folds
from app.config import get_settings
from app.history_sync import load_m5_candles
from app.local_dataset import DatasetRelease
from app.regime import build_regime_timeline, regime_at
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse
from app.strategies.zigzag_v7 import context

def main():
    root = Path(__file__).resolve().parents[1]
    settings = get_settings()
    source = HistoricalReplayResponse.model_validate_json((root / 'data/backtests/core-zigzag-v5-365.json').read_text())
    release = DatasetRelease.open(settings.lotus_data_root, settings.lotus_dataset_version)
    candles = load_m5_candles(release, 'XAUUSD', 1095)
    closes = [c.timestamp_utc + timedelta(minutes=5) for c in candles]
    timeline = build_regime_timeline(candles, settings)
    kept = []
    for trade in source.trades:
        index = bisect_right(closes, trade.opened_at_utc)
        allowed, checks, metadata = context(candles[max(0,index-4000):index], trade.opened_at_utc, trade.side.value, settings, regime_at(timeline, trade.opened_at_utc))
        if allowed:
            kept.append(trade.model_copy(update={'trade_id': trade.trade_id.replace('core-zigzag-v5','core-zigzag-v7'), 'setup': 'zigzag_v7_directional_intersection', 'note': trade.note + ' V7: interseção exploratória, saídas e volumes herdados da V5.'}))
    snapshot = build_results_snapshot([t.model_dump(mode='json') for t in kept], 'v7-exploratory-intersection')
    expectancy, dd, streak, costs = _risk_diagnostics(kept)
    output = source.model_copy(update={'bot_id':'core-zigzag-v7','strategy_version':'v7-directional-1','settings_fingerprint':'v7-exploratory-intersection-1','trades':kept,'summary':snapshot.summary,'daily_pnl':snapshot.daily_pnl,'expectancy_r':expectancy,'max_drawdown_r':dd,'max_consecutive_losses':streak,'total_costs':costs,'candidates_detected':len(source.trades),'candidates_eligible':len(kept),'candidates_blocked':len(source.trades)-len(kept),'blocked_reasons':{'v7_directional_gate':len(source.trades)-len(kept)},'regime_counts':{},'validation_folds':_validation_folds(kept,source.period_start_utc,source.period_end_utc,30),'validation_status':'provisional_shadow','validation_reason':'Exploratory intersection; requires independent replay with regenerated signals, exits and position sizing.','assumptions':source.assumptions+['V7: somente candles com fechamento <= entrada. Fills e volumes herdados; resultado exploratório, sem validação independente.']})
    (root / 'data/backtests/core-zigzag-v7-365.json').write_text(output.model_dump_json(indent=2)+'\n')
    print(len(kept), snapshot.summary.win_rate_pct, snapshot.summary.profit_factor)

if __name__ == '__main__':
    main()
