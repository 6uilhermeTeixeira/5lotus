"""FastAPI application serving coverage and viewport-bounded market series."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from lotus.data.market import aggregate_ticks, choose_resolution, hour_from_path, serialize_ticks
from lotus.data.parquet import ParquetReleaseReader
from lotus.collection import progress_snapshot
from lotus.paths import MANIFEST_ROOT, PROJECT_ROOT, RAW_ROOT

PROJECT_ROOT = Path(os.getenv("LOTUS_PROJECT_ROOT", PROJECT_ROOT))
MANIFEST = MANIFEST_ROOT / "dukascopy.sqlite3"
WEB_DIST = PROJECT_ROOT / "dist"
PARQUET = ParquetReleaseReader()
UTC = dt.timezone.utc

app = FastAPI(title="1lotus Market Data API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def parse_instant(value: str) -> int:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1_000)
    except ValueError as exc:
        raise HTTPException(422, f"invalid ISO timestamp: {value}") from exc


def paths_for_range(instrument: str, from_ms: int, to_ms: int):
    base = RAW_ROOT / instrument
    if not base.is_dir():
        raise HTTPException(404, "instrument not found")
    for path in sorted(base.glob("**/*h_ticks.bi5")):
        try:
            hour_ms = int(hour_from_path(path).timestamp() * 1_000)
        except (ValueError, IndexError):
            continue
        if hour_ms < to_ms and hour_ms + 3_600_000 > from_ms and path.stat().st_size > 0:
            yield path, hour_ms


def ticks_for_range(instrument: str, from_ms: int, to_ms: int):
    yield from PARQUET.ticks(instrument, from_ms, to_ms)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "raw_root": str(RAW_ROOT), "manifest": MANIFEST.exists()}


@app.get("/api/v1/coverage/{instrument}")
def coverage(instrument: str):
    instrument = instrument.upper()
    base = RAW_ROOT / instrument
    files = list(base.glob("**/*h_ticks.bi5")) if base.exists() else []
    nonempty = [path for path in files if path.stat().st_size > 0]
    first = min((hour_from_path(path) for path in nonempty), default=None)
    last = max((hour_from_path(path) for path in nonempty), default=None)
    statuses: dict[str, int] = {}
    ticks = 0
    updated = None
    if MANIFEST.exists():
        db = sqlite3.connect(f"file:{MANIFEST}?mode=ro", uri=True)
        statuses = dict(db.execute(
            "SELECT status,count(*) FROM downloads WHERE instrument=? GROUP BY status", (instrument,)
        ))
        row = db.execute(
            "SELECT coalesce(sum(records),0),max(updated_at) FROM downloads WHERE instrument=?", (instrument,)
        ).fetchone()
        ticks, updated = row
        db.close()
    requested_start = dt.date.fromisoformat(os.getenv("LOTUS_COLLECTION_START", "2003-05-05"))
    requested_end = dt.date.fromisoformat(
        os.getenv("LOTUS_COLLECTION_END", str(dt.datetime.now(UTC).date() - dt.timedelta(days=1)))
    )
    progress = progress_snapshot(MANIFEST, instrument, requested_start, requested_end)
    return {
        "instrument": instrument,
        "first_hour": first.isoformat() if first else None,
        "last_hour": last.isoformat() if last else None,
        "files": len(files), "nonempty_files": len(nonempty), "ticks_manifest": ticks,
        "statuses": statuses, "updated_at": updated, "progress": progress,
    }


@app.get("/api/v1/series/{instrument}")
def series(
    instrument: str,
    from_: str = Query(alias="from"),
    to: str = Query(...),
    resolution: str = Query("auto"),
    mode: Literal["candles", "ticks"] = Query("candles"),
    price_type: Literal["mid", "bid", "ask"] = Query("mid"),
    viewport_px: int = Query(1_400, ge=320, le=4_000),
):
    instrument = instrument.upper()
    from_ms, to_ms = parse_instant(from_), parse_instant(to)
    if from_ms >= to_ms:
        raise HTTPException(422, "from must be before to")
    if to_ms - from_ms > 40 * 366 * 86_400_000:
        raise HTTPException(422, "range exceeds 40 years")
    try:
        effective = "tick" if mode == "ticks" and resolution in ("tick", "auto") else choose_resolution(from_ms, to_ms, viewport_px, resolution)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    ticks = ticks_for_range(instrument, from_ms, to_ms)
    if effective == "tick":
        if to_ms - from_ms > 6 * 3_600_000:
            raise HTTPException(422, "tick mode is limited to six hours; zoom in or select a candle resolution")
        data, truncated = serialize_ticks(ticks)
        response_mode = "ticks"
    else:
        data = PARQUET.candles(instrument, effective, from_ms, to_ms) if price_type == "mid" else None
        if data is None:
            data = aggregate_ticks(ticks, effective, price_type)
        truncated = len(data) > 5_000
        if truncated:
            data = data[:5_000]
        response_mode = "candles"
    return {
        "instrument": instrument, "mode": response_mode,
        "requested_resolution": resolution, "effective_resolution": effective,
        "price_type": price_type, "from_ms": from_ms, "to_ms": to_ms,
        "dataset_version": PARQUET.version,
        "count": len(data), "truncated": truncated, "data": data,
    }


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
