"""Build the causal tick replay for ZigZag Scalper V1.2.

V1.2 keeps the original M30 fractal breakout and V1 lifecycle.  The entry is
delayed until the first causal tick sequence that breaks, retests the pivot,
and rejects in the breakout direction.  Missing or incomplete tick days are
not interpolated.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import duckdb
import numpy as np

from app.backtest import _risk_diagnostics, _validation_folds, replay_settings_fingerprint
from app.config import get_settings
from app.local_backtest_store import save_local_backtest
from app.local_dataset import DatasetRelease, file_sha256
from app.results_store import build_results_snapshot, load_bots_catalog
from app.schemas import HistoricalReplayResponse, TradeResult
from app.strategies.zigzag_v4_research import exit_trade
from scripts.research_zigzag_v4_raw_ticks import features, prepare_candles


ROOT = Path(__file__).resolve().parents[1]
BOT_ID = "core-zigzag-v12"
PIP_SIZE = 0.01


def iso(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, UTC).isoformat()


def v12_entries(t, bid, ask, f, direction, *, max_age_ms=90_000, max_depth_pips=50.0,
               retest_tolerance_pips=10.0, rejection_pips=5.0):
    """Return (breakout_index, rejection_index, pivot) without future data."""
    level = f["high"] if direction == 1 else f["low"]
    quote = ask if direction == 1 else bid
    previous = f["prior"]
    base = (
        f["valid"] & np.isfinite(level) & np.isfinite(previous)
        & (f["spread"] <= 0.5)
        & ((t // 3_600_000 % 24) >= 3) & ((t // 3_600_000 % 24) < 19)
        & (direction * (previous - level) <= 0)
        & (direction * (quote - level) > 0)
    )
    breakouts = np.flatnonzero(base)
    results = []
    used_buckets = set()
    tolerance = retest_tolerance_pips * PIP_SIZE
    max_depth = max_depth_pips * PIP_SIZE
    min_rejection = rejection_pips * PIP_SIZE
    for start in breakouts:
        bucket = int(f["bucket"][start])
        if bucket in used_buckets:
            continue
        end = int(np.searchsorted(t, t[start] + max_age_ms, side="right"))
        pivot = float(level[start])
        retest = False
        for index in range(start + 1, min(end, len(t))):
            if direction == 1:
                touched = pivot - max_depth <= bid[index] <= pivot + tolerance
                rejected = ask[index] >= pivot + min_rejection
            else:
                touched = pivot - tolerance <= ask[index] <= pivot + max_depth
                rejected = bid[index] <= pivot - min_rejection
            if touched:
                retest = True
            if retest and rejected:
                results.append((int(start), int(index), pivot))
                used_buckets.add(bucket)
                break
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor", default="2026-09-02T00:00:00+00:00")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--release", default="CURRENT")
    parser.add_argument("--output", type=Path, default=ROOT / "data/research/zigzag-v12-tick-replay")
    args = parser.parse_args()
    end_dt = datetime.fromisoformat(args.anchor)
    end = int(end_dt.timestamp() * 1000)
    start = int((end_dt - timedelta(days=args.days)).timestamp() * 1000)
    release = DatasetRelease.open(Path("/home/codexops/lotus-data"), args.release)
    args.output.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET threads=2")
    candles, candle_sources = prepare_candles(connection, release, start, end)
    partitions = [row for row in release.manifest["partitions"] if iso(start)[:10] <= row["day"] <= iso(end)[:10]]
    all_rows = []
    coverage = []
    base_candidates = eligible_candidates = 0
    for number, source in enumerate(partitions, 1):
        path = release.root / source["path"]
        if file_sha256(path) != source["sha256"]:
            raise ValueError("tick hash mismatch: " + source["day"])
        data = connection.execute(
            "SELECT timestamp_ms,bid,ask FROM read_parquet(?, file_row_number=true) ORDER BY timestamp_ms,file_row_number",
            [str(path)],
        ).fetchnumpy()
        t, bid, ask = (data[key] for key in ("timestamp_ms", "bid", "ask"))
        valid = np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask >= bid)
        t, bid, ask = t[valid], bid[valid], ask[valid]
        if not len(t):
            continue
        scope = (t >= start) & (t < end)
        coverage.append({"day": source["day"], "ticks": int(scope.sum()), "sha256": source["sha256"],
                         "first_ms": int(t[0]), "last_ms": int(t[-1]),
                         "gaps_over_60s": int((np.diff(t) > 60_000).sum())})
        f = features(t, bid, ask, candles)
        f["valid"] &= scope
        choices = []
        for direction in (1, -1):
            found = v12_entries(t, bid, ask, f, direction)
            level = f["high"] if direction == 1 else f["low"]
            quote = ask if direction == 1 else bid
            base_mask = (
                f["valid"] & np.isfinite(level) & np.isfinite(f["prior"])
                & (f["spread"] <= 0.5)
                & ((t // 3_600_000 % 24) >= 3) & ((t // 3_600_000 % 24) < 19)
                & (direction * (f["prior"] - level) <= 0)
                & (direction * (quote - level) > 0)
            )
            # A breakout remains true across many ticks. Count its first
            # observation once per M5 bucket, matching the V1 event contract.
            seen_buckets = set()
            for index in np.flatnonzero(base_mask):
                bucket = int(f["bucket"][index])
                if bucket not in seen_buckets:
                    base_candidates += 1
                    seen_buckets.add(bucket)
            choices.extend((signal, rejection, direction, pivot) for signal, rejection, pivot in found)
        choices.sort(key=lambda row: row[1])
        occupied_until = -1
        for signal, entry_index, direction, pivot in choices:
            if entry_index <= occupied_until:
                continue
            result = exit_trade(
                t, bid, ask, entry_index, direction,
                stop=2.4, target=10.0, be=0.4, offset=0.0,
                activation=1.2, trail=0.6, hold_ms=600_000,
                slippage=0.02, risk_usd=24.0,
            )
            opened = datetime.fromtimestamp(result["entry_ms"] / 1000, UTC)
            closed = datetime.fromtimestamp(result["exit_ms"] / 1000, UTC)
            side = "buy" if direction == 1 else "sell"
            all_rows.append(TradeResult(
                trade_id=f"tick-replay:{BOT_ID}:{len(all_rows) + 1}", symbol="XAUUSD", timeframe="M5",
                setup="zigzag_v12_micro_retest_rejection", side=side,
                opened_at_utc=opened, closed_at_utc=closed, volume_lots=result["lot"],
                entry_price=result["entry"], exit_price=result["exit"],
                stop_loss_price=result["entry"] - direction * 2.4,
                take_profit_price=result["entry"] + direction * 10.0,
                risk_amount=24.0, gross_pnl=result["net_pnl"], fees=result["fees"],
                net_pnl=result["net_pnl"], rr_realized=result["r"],
                note=(f"Causal tick replay; pivot={pivot:.5f}; retest_age_ms={int(t[entry_index] - t[signal])}; "
                      f"retest_depth_limit=50 pips; no order sent."),
            ))
            eligible_candidates += 1
            occupied_until = result["exit_ms"]
        if number % 25 == 0 or number == len(partitions):
            print(json.dumps({"progress": f"{number}/{len(partitions)}", "days": len(coverage),
                              "trades": len(all_rows)}), flush=True)

    all_rows.sort(key=lambda row: row.closed_at_utc or row.opened_at_utc)
    snapshot = build_results_snapshot([row.model_dump(mode="json") for row in all_rows], "zigzag-v12-tick-replay")
    expectancy, drawdown, streak, costs = _risk_diagnostics(all_rows)
    bots = {bot.id: bot for bot in load_bots_catalog(get_settings().bots_catalog_path)}
    bot = bots[BOT_ID]
    replay = HistoricalReplayResponse(
        bot_id=BOT_ID, symbol=bot.symbol, timeframe=bot.timeframe,
        risk_per_trade_pct=get_settings().backtest_risk_per_trade_pct,
        strategy_version="v1.2-causal-tick-micro-retest-1",
        settings_fingerprint=replay_settings_fingerprint(get_settings(), bot),
        period_start_utc=end_dt - timedelta(days=args.days), period_end_utc=end_dt,
        candles_evaluated=len(candles["t"]), candidates_detected=base_candidates,
        candidates_eligible=eligible_candidates,
        candidates_blocked=max(0, base_candidates - eligible_candidates),
        blocked_reasons={"micro_retest_not_confirmed": max(0, base_candidates - eligible_candidates)},
        expectancy_r=expectancy, max_drawdown_r=drawdown, max_consecutive_losses=streak,
        total_costs=costs, validation_status="provisional_shadow",
        validation_reason="causal tick replay; requires holdout, stress costs and Fusion forward validation",
        validation_folds=_validation_folds(all_rows, end_dt - timedelta(days=args.days), end_dt, 30),
        assumptions=[
            "Pivôs M30 causais e geometria de entrada preservados da V1.",
            "Microreteste: Bid/Ask retorna até 10 pips acima do pivô ou até 50 pips abaixo/acima em profundidade, seguido de rejeição mínima de 5 pips em até 90 segundos.",
            "Stop 240 pontos, alvo 1000 pontos, breakeven 40 pontos, trailing 120/60 pontos e holding máximo de 600 segundos.",
            "Entrada e saída usam Bid/Ask, spread observado e slippage modelado de 2 pontos; risco fixo de US$24 e comissão do helper de pesquisa.",
            "Uma entrada por M5 e uma posição aberta por vez; dias sem ticks não são interpolados.",
        ],
        summary=snapshot.summary, daily_pnl=snapshot.daily_pnl, trades=all_rows,
    )
    save_local_backtest(get_settings().backtest_cache_path, replay, args.days)
    report = {"bot_id": BOT_ID, "dataset": release.version, "anchor": end_dt.isoformat(),
              "days": args.days, "coverage": coverage, "total_ticks": sum(x["ticks"] for x in coverage),
              "candidates_detected": base_candidates, "candidates_eligible": eligible_candidates,
              "summary": snapshot.summary.model_dump(mode="json"), "expectancy_r": expectancy,
              "max_drawdown_r": drawdown, "validation_status": replay.validation_status,
              "validation_reason": replay.validation_reason, "assumptions": replay.assumptions,
              "candle_sources": candle_sources}
    (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (args.output / "trades.json").write_text(json.dumps([row.model_dump(mode="json") for row in all_rows], indent=2) + "\n")
    print(json.dumps({"output": str(get_settings().backtest_cache_path / f"{BOT_ID}-{args.days}.json"),
                      "trades": len(all_rows), "summary": report["summary"],
                      "candidates_detected": base_candidates, "candidates_eligible": eligible_candidates}, indent=2), flush=True)


if __name__ == "__main__":
    main()
