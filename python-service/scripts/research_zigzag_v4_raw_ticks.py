"""One-year raw-tick V3 audit and bounded V4 experiment, no production writes.

Run with PYTHONPATH=. .venv/bin/python scripts/research_zigzag_v4_raw_ticks.py
--anchor 2026-09-11T20:55:00+00:00 --output data/research/zigzag-v4-raw-20260913
The anchor is the close of the latest saved M5, not the publication date.
Missing tick days remain missing; no candle interpolation or source splicing.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import duckdb
import numpy as np

from app.local_dataset import DatasetRelease, file_sha256
from app.strategies.zigzag_v4_research import CANDIDATES, exit_trade, persistence


ROOT = Path(__file__).resolve().parents[1]


def iso(ms):
    return datetime.fromtimestamp(int(ms) / 1000, UTC).isoformat()


def metrics(rows):
    rows = sorted(rows, key=lambda x: x["exit_ms"])
    r = np.array([x["r"] for x in rows], dtype=float)
    equity = np.r_[0, np.cumsum(r)]
    loss = -r[r < 0].sum()
    return {
        "trades": len(rows), "net_r": round(float(r.sum()), 4),
        "net_usd_at_24_risk": round(float(r.sum() * 24), 2),
        "expectancy_r": round(float(r.mean()), 5) if len(r) else None,
        "profit_factor": round(float(r[r > 0].sum() / loss), 4) if loss else None,
        "win_rate_pct": round(float((r > 0).mean() * 100), 2) if len(r) else None,
        "max_drawdown_r": round(float((np.maximum.accumulate(equity) - equity).max()), 4),
        "worst_r": round(float(r.min()), 4) if len(r) else None,
        "best_r": round(float(r.max()), 4) if len(r) else None,
    }


def prepare_candles(connection, release, start, end):
    rows = [x for x in release.manifest["aggregations"]["5m"] if
            iso(start - 14 * 86400000)[:10] <= x["day"] <= iso(end)[:10]]
    for row in rows:
        if file_sha256(release.root / row["path"]) != row["sha256"]:
            raise ValueError("M5 hash mismatch: " + row["day"])
    values = connection.execute(
        "SELECT t,o,h,l,c FROM read_parquet(?) ORDER BY t",
        [[str(release.root / x["path"]) for x in rows]],
    ).fetchnumpy()
    t, hi, lo, close = (values[k] for k in ("t", "h", "l", "c"))
    if np.any(np.diff(t) <= 0):
        raise ValueError("M5 timestamps not unique")
    # Context at M5 OPEN: only completed candles, strict six-candle M30 buckets.
    m30 = []
    for bucket in np.unique(t // 1800000):
        ix = np.flatnonzero(t // 1800000 == bucket)
        if len(ix) == 6 and t[ix[0]] == bucket * 1800000:
            m30.append((bucket * 1800000, hi[ix].max(), lo[ix].min()))
    m30 = np.array(m30)
    high = np.full(len(t), np.nan)
    low = high.copy()
    ranges = high.copy()
    prior = high.copy()
    ema_seed = high.copy()
    for i in range(60, len(t)):
        ranges[i] = np.mean(hi[i-60:i] - lo[i-60:i])
        prior[i] = close[i-1]
        e = close[i-19]
        for price in close[i-18:i]:
            e = price * 2 / 21 + e * 19 / 21
        ema_seed[i] = e
        available = m30[(m30[:, 0] >= t[i-60]) & (m30[:, 0] + 1800000 <= t[i])]
        for j in range(2, len(available) - 2):
            if available[j, 1] == available[j-2:j+3, 1].max():
                high[i] = available[j, 1]
            if available[j, 2] == available[j-2:j+3, 2].min():
                low[i] = available[j, 2]
    return {"t": t, "high": high, "low": low, "range": ranges,
            "prior": prior, "ema_seed": ema_seed}, rows


def features(t, bid, ask, candles):
    index = np.searchsorted(candles["t"], t // 300000 * 300000)
    index = np.minimum(index, len(candles["t"]) - 1)
    valid = candles["t"][index] == t // 300000 * 300000
    mid = (bid + ask) / 2
    path = np.r_[0, np.cumsum(np.abs(np.diff(mid)))]
    result = {k: v[index] for k, v in candles.items() if k != "t"}
    result.update({"spread": ask-bid, "mid": mid, "bucket": t // 300000, "valid": valid})
    for seconds in (5, 30, 900):
        ix = np.searchsorted(t, t-seconds*1000, side="right")-1
        ready = (ix >= 0) & (t-np.take(t, np.maximum(ix, 0)) <= seconds*1000 + 2000)
        ix = np.maximum(ix, 0)
        result[f"move{seconds}"] = mid - mid[ix]
        result[f"ready{seconds}"] = ready
        if seconds == 30:
            length = path-path[ix]
            result["efficiency"] = np.divide(abs(mid-mid[ix]), length, out=np.zeros(len(t)), where=length>0)
            result["path30"] = length
    return result


def entry_indices(t, bid, ask, f, candidate, direction):
    level = f["high"] if direction == 1 else f["low"]
    quote = ask if direction == 1 else bid
    opposite = bid if direction == 1 else ask
    extension = direction * (quote-level)
    expanded = f["range"] >= 6
    # Current forming M5 close is current midpoint; preceding 19 closes are final.
    ema = f["mid"] * 2/21 + f["ema_seed"] * 19/21
    structural = (f["ready900"] & (direction*f["move900"] >= 10)
                  & (direction*(f["mid"]-ema) >= 9) & (extension <= .5)
                  & (((t // 86400000 + 3) % 7) != 4))
    mask = (f["valid"] & np.isfinite(f["range"]) & (f["spread"] <= .5)
            & ((t // 3600000 % 24) >= 3) & ((t // 3600000 % 24) < 19)
            & (direction*(f["prior"]-level) <= 0) & (extension > 0)
            & (~expanded | structural))
    if candidate.confirm_quote:
        beyond = direction*(opposite-level) > 0
        mask &= beyond
        if candidate.persistence_ms:
            mask &= persistence(t, beyond, f["bucket"]) >= candidate.persistence_ms
    if candidate.efficiency_min:
        mask &= (f["ready30"] & f["ready5"] & (f["efficiency"] >= candidate.efficiency_min)
                 & (direction*f["move5"] >= f["spread"])
                 & (extension <= np.maximum(.1, np.minimum(.5, .15*f["range"]))))
    return np.flatnonzero(mask)


def replay_indices(t, bid, ask, f, indices, candidate, latency, slip):
    output = []
    # One signal per M5 and one open position; later eligible ticks can enter once
    # a preceding position closes. No search restricted to old winning entries.
    if not len(indices):
        return output
    signal_times = t[indices[:, 0]]
    cursor = 0
    while cursor < len(indices):
        signal, direction = map(int, indices[cursor])
        cursor += 1
        fill = int(np.searchsorted(t, t[signal]+latency, side="left"))
        if fill >= len(t) or t[fill] - t[signal] > latency + 2000:
            continue
        expanded = bool(f["range"][signal] >= 6)
        stop = .6 if expanded else 2.4
        be, offset, activation, trail, hold = (.4, .01, .4, .2, 60000) if expanded else (.4, 0, 1.2, .6, 600000)
        if candidate.scaled_exit:
            stop = float(np.clip(.5*f["range"][signal], .6, 4.8))
            be, offset, activation, trail = stop/6, 0, stop/2, stop/4
        row = exit_trade(t, bid, ask, fill, direction, stop=stop, be=be, offset=offset,
                         activation=activation, trail=trail, hold_ms=hold, slippage=slip)
        row.update({"signal_ms": int(t[signal]), "mode": "expansion" if expanded else "normal",
                    "range60": float(f["range"][signal]), "spread": float(f["spread"][signal]),
                    "efficiency30": float(f["efficiency"][signal]),
                    "move5_aligned": float(direction*f["move5"][signal]),
                    "path30": float(f["path30"][signal])})
        next_time = max(row["exit_ms"]+1, (int(f["bucket"][signal])+1)*300000)
        cursor = int(np.searchsorted(signal_times, next_time, side="left"))
        output.append(row)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release", default="CURRENT")
    args = parser.parse_args()
    end_date = datetime.fromisoformat(args.anchor)
    end = int(end_date.timestamp()*1000)
    start = int((end_date-timedelta(days=365)).timestamp()*1000)
    split = start+182*86400000
    release = DatasetRelease.open(Path("/home/codexops/lotus-data"), args.release)
    args.output.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET threads=2")
    candles, candle_sources = prepare_candles(connection, release, start, end)
    partitions = [x for x in release.manifest["partitions"] if iso(start)[:10] <= x["day"] <= iso(end)[:10]]
    old_path = ROOT/"data/backtests-operational/core-zigzag-v3-365.json"
    old = json.loads(old_path.read_text())["trades"]
    historical = []
    for row in old:
        ms = int(datetime.fromisoformat(row["opened_at_utc"].replace("Z", "+00:00")).timestamp()*1000)
        if start <= ms < end:
            historical.append((ms, row))
    protocol = {
        "dataset": release.version, "anchor_close_utc": iso(end), "requested_start_utc": iso(start),
        "selection_end_utc": iso(split), "candidates": [asdict(x) for x in CANDIDATES],
        "selection": "Highest training net R / max(drawdown R, 1), >=50 trades and PF>1.05; otherwise reject.",
        "execution": "Bid/Ask ticks, $24 initial risk, 100 oz/lot, $4.50 commission/lot round turn; fractional lots; no compounding",
        "scenarios": {"base": {"latency_ms": 250, "slippage_usd_each_market_fill": .02},
                      "stress": {"latency_ms": 1000, "slippage_usd_each_market_fill": .05}},
        "limitations": ["Historical holdouts were studied previously: out-of-selection, not untouched market evidence.",
                        "Tick V3 reconstructs entries causally; it is not identical to archived candle replay.",
                        "Strict complete M30 buckets, forming candle midpoint, one signal per M5 are explicit replay contracts.",
                        "Stop amendments take effect on next quote; no broker amendment/network latency simulation.",
                        "No swaps, margin rejection, stop-distance limits or lot-step rounding; research only."],
        "historical_snapshot_sha256": file_sha256(old_path),
        "source_hashes": {str(p.relative_to(ROOT)): file_sha256(p) for p in
                          (Path(__file__), ROOT/"app/strategies/zigzag_v4_research.py")},
    }
    (args.output/"protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    tracks = {f"{c.name}:{s}": [] for c in CANDIDATES for s in protocol["scenarios"]}
    audit, coverage = [], []
    for day_no, source in enumerate(partitions):
        path = release.root/source["path"]
        if file_sha256(path) != source["sha256"]:
            raise ValueError("Tick hash mismatch: "+source["day"])
        data = connection.execute("SELECT timestamp_ms,bid,ask FROM read_parquet(?, file_row_number=true) ORDER BY timestamp_ms,file_row_number", [str(path)]).fetchnumpy()
        t,bid,ask = (data[k] for k in ("timestamp_ms","bid","ask"))
        good = np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask >= bid)
        invalid = int((~good).sum())
        t,bid,ask = t[good],bid[good],ask[good]
        if not len(t):
            continue
        scope = (t >= start) & (t < end)
        coverage.append({"day": source["day"], "ticks": int(scope.sum()), "invalid_quotes": invalid,
                         "first_ms": int(t[0]), "last_ms": int(t[-1]), "sha256": source["sha256"],
                         "active_hours": len(np.unique(t[scope]//3600000)),
                         "gaps_over_60s": int((np.diff(t)>60000).sum()),
                         "max_gap_ms": int(np.diff(t).max()) if len(t)>1 else 0,
                         "median_spread": float(np.median(ask-bid)), "p95_spread": float(np.quantile(ask-bid,.95))})
        f = features(t,bid,ask,candles)
        f["valid"] &= scope
        for c in CANDIDATES:
            # Every eligible raw tick is retained. Binary search skips only
            # already-occupied time and an M5 that has consumed its signal.
            choices = []
            for d in (1,-1):
                idx = entry_indices(t,bid,ask,f,c,d)
                if len(idx):
                    choices.append(np.column_stack((idx, np.full(len(idx),d))))
            choices = np.concatenate(choices) if choices else np.empty((0,2),dtype=int)
            if len(choices):
                choices = choices[np.argsort(choices[:,0],kind="stable")]
            for scenario,p in protocol["scenarios"].items():
                tracks[f"{c.name}:{scenario}"].extend(replay_indices(t,bid,ask,f,choices,c,p["latency_ms"],p["slippage_usd_each_market_fill"]))
        for ms,old_row in historical:
            if not t[0] <= ms <= t[-1]:
                continue
            i = int(np.searchsorted(t,ms,side="right"))-1
            if i<0 or ms-t[i]>2000 or not np.isfinite(f["range"][i]):
                continue
            risk = float(old_row.get("risk_amount") or 24)
            row = {"entry_ms":ms,"exit_ms":int(datetime.fromisoformat(old_row["closed_at_utc"].replace("Z","+00:00")).timestamp()*1000),
                   "r":float(old_row["net_pnl"])/risk,"original_net_pnl":float(old_row["net_pnl"]),
                   "original_risk":risk,"direction":1 if old_row["side"]=="buy" else -1,
                   "range60":float(f["range"][i]),"spread":float(f["spread"][i]),
                   "efficiency30":float(f["efficiency"][i]),"path30":float(f["path30"][i])}
            fill = int(np.searchsorted(t,ms+250))
            expanded = f["range"][i]>=6
            if fill<len(t) and t[fill]-ms<=2250:
                tick = exit_trade(t,bid,ask,fill,row["direction"],stop=.6 if expanded else 2.4,
                                  be=.4,offset=.01 if expanded else 0,
                                  activation=.4 if expanded else 1.2,trail=.2 if expanded else .6,
                                  hold_ms=60000 if expanded else 600000)
                row["same_timestamp_tick_r"] = tick["r"]
                row["tick_mfe_r"],row["tick_mae_r"] = tick["mfe_r"],tick["mae_r"]
            audit.append(row)
        if day_no%15==0 or day_no==len(partitions)-1:
            print(json.dumps({"day":source["day"],"progress":f"{day_no+1}/{len(partitions)}",
                              "ticks":sum(x["ticks"] for x in coverage),
                              "trades":{k:len(v) for k,v in tracks.items() if k.endswith(":base")}}),flush=True)
    # Training is purged of positions crossing the chronological split.
    def periods(rows):
        return {"training":metrics([x for x in rows if x["exit_ms"]<split]),
                "holdout":metrics([x for x in rows if x["entry_ms"]>=split]),"overall":metrics(rows)}
    summary = {k:periods(v) for k,v in tracks.items()}
    eligible = [c.name for c in CANDIDATES[1:] if summary[c.name+":base"]["training"]["trades"]>=50
                and (summary[c.name+":base"]["training"]["profit_factor"] or 0)>1.05]
    def score(name):
        m=summary[name+":base"]["training"]
        return m["net_r"]/max(m["max_drawdown_r"],1)
    selected = max(eligible,key=score) if eligible else None
    selected_for_diagnosis = selected or max((c.name for c in CANDIDATES[1:]),key=score)
    # Descriptive groups use training-only boundaries and are not selection inputs.
    groups = {}
    for family,rows in [("archived_v3",audit),("v3_ticks",tracks["v3_ticks:base"]),
                        ("selected_v4",tracks[selected_for_diagnosis+":base"])]:
        groups[family]={}
        training=[x for x in rows if x["exit_ms"]<split]
        for feature in ("range60","spread","efficiency30","path30"):
            if not training:
                continue
            edges=np.quantile([x[feature] for x in training],[.25,.5,.75])
            groups[family][feature]={"training_quartile_edges":edges.tolist(),"quartiles":[
                periods([x for x in rows if np.searchsorted(edges,x[feature],side="right")==q]) for q in range(4)]}
    hold = summary[selected_for_diagnosis+":base"]["holdout"]
    stress = summary[selected_for_diagnosis+":stress"]["holdout"]
    baseline = summary["v3_ticks:base"]["holdout"]
    accepted = bool(selected and hold["trades"]>=50 and (hold["profit_factor"] or 0)>1
                    and stress["net_r"]>0 and hold["net_r"]>baseline["net_r"])
    report = {**protocol,"coverage":coverage,"total_ticks":sum(x["ticks"] for x in coverage),
              "observed_start_utc":iso(max(start,min(x["first_ms"] for x in coverage))),
              "observed_end_utc":iso(min(end,max(x["last_ms"] for x in coverage))),
              "results":summary,"selected_on_training":selected,"best_training_diagnostic":selected_for_diagnosis,
              "decision":"forward_candidate_only" if accepted else "rejected",
              "descriptive_volatility_groups":groups,"historical_matched":len(audit),
              "historical_total_in_requested_window":len(historical),
              "historical_best_10":sorted(audit,key=lambda x:x["r"],reverse=True)[:10],
              "historical_worst_10":sorted(audit,key=lambda x:x["r"])[:10],
              "tick_v3_best_10":sorted(tracks["v3_ticks:base"],key=lambda x:x["r"],reverse=True)[:10],
              "tick_v3_worst_10":sorted(tracks["v3_ticks:base"],key=lambda x:x["r"])[:10],
              "candle_sources":candle_sources}
    for key,value in [("report.json",report),("trades.json",tracks),("historical_audit.json",audit)]:
        (args.output/key).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"selected":selected,"decision":report["decision"],"results":summary},indent=2),flush=True)
    connection.close()


if __name__ == "__main__":
    main()
