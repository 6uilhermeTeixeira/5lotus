#!/usr/bin/env python3
"""Publish validated Dukascopy ticks as immutable, versioned Parquet releases."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq

from lotus.data.market import aggregate_ticks, decode_bi5, hour_from_path
from lotus.paths import CURATED_ROOT, DERIVED_ROOT, MANIFEST_ROOT, RAW_ROOT, RELEASES_ROOT

SCHEMA_VERSION = "xauusd-ticks-v1"
AGGREGATE_RESOLUTIONS = ("1s", "1m", "5m", "1h", "1d")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2, sort_keys=True)
            target.write("\n")
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def write_content_addressed(table: pa.Table, objects: Path, prefix: str) -> tuple[Path, str]:
    objects.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{prefix}.", suffix=".parquet.part", dir=objects)
    os.close(fd)
    temporary = Path(temporary_name)
    pq.write_table(table, temporary, compression="zstd", row_group_size=250_000)
    digest = sha256(temporary)
    target = objects / f"{digest}.parquet"
    if target.exists():
        temporary.unlink()
    else:
        os.replace(temporary, target)
    return target, digest


def publish_day(instrument: str, paths: list[Path], day: dt.date) -> tuple[Path, int, str, dict[str, dict[str, object]]]:
    ticks = []
    for path in sorted(paths):
        ticks.extend(decode_bi5(path, int(hour_from_path(path).timestamp() * 1_000)))
    table = pa.table({
        "timestamp_ms": pa.array((tick.timestamp_ms for tick in ticks), type=pa.int64()),
        "bid": pa.array((tick.bid for tick in ticks), type=pa.float64()),
        "ask": pa.array((tick.ask for tick in ticks), type=pa.float64()),
        "bid_volume": pa.array((tick.bid_volume for tick in ticks), type=pa.float64()),
        "ask_volume": pa.array((tick.ask_volume for tick in ticks), type=pa.float64()),
        "source": pa.array(("dukascopy" for _ in ticks), type=pa.dictionary(pa.int8(), pa.string())),
    })
    target, digest = write_content_addressed(table, CURATED_ROOT / "objects", f"{instrument}-{day}")
    aggregates: dict[str, dict[str, object]] = {}
    for resolution in AGGREGATE_RESOLUTIONS:
        rows = aggregate_ticks(ticks, resolution, "mid")
        aggregate_table = pa.Table.from_pylist(rows)
        aggregate_path, aggregate_hash = write_content_addressed(
            aggregate_table, DERIVED_ROOT / "ohlcv" / resolution / "objects", f"{instrument}-{day}",
        )
        aggregates[resolution] = {
            "path": str(aggregate_path.relative_to(CURATED_ROOT.parent)), "bytes": aggregate_path.stat().st_size,
            "rows": len(rows), "sha256": aggregate_hash, "instrument": instrument, "day": day.isoformat(),
            "price_type": "mid",
        }
    return target, len(ticks), digest, aggregates


def collection_snapshot(instrument: str, start: dt.date, end: dt.date) -> dict[str, object]:
    expected = ((end - start).days + 1) * 24
    counts: dict[str, int] = {}
    updated_at = None
    manifest_path = MANIFEST_ROOT / "dukascopy.sqlite3"
    if manifest_path.exists():
        database = sqlite3.connect(f"file:{manifest_path}?mode=ro", uri=True)
        counts = dict(database.execute(
            "SELECT status,count(*) FROM downloads WHERE instrument=? GROUP BY status", (instrument,)
        ))
        row = database.execute(
            "SELECT max(updated_at) FROM downloads WHERE instrument=?", (instrument,)
        ).fetchone()
        updated_at = row[0] if row else None
        database.close()
    terminal = sum(counts.get(status, 0) for status in ("downloaded", "existing", "missing"))
    complete = terminal >= expected and counts.get("retry", 0) == 0
    return {
        "status": "complete" if complete else "partial",
        "coverage_complete": complete,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "expected_hours": expected,
        "terminal_hours": terminal,
        "progress_pct": round(min(100.0, terminal * 100 / expected), 4) if expected else 100.0,
        "statuses": counts,
        "updated_at": updated_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument", default="XAUUSD")
    parser.add_argument("--requested-start", type=dt.date.fromisoformat, default=dt.date(2003, 5, 5))
    parser.add_argument("--requested-end", type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))
    args = parser.parse_args()
    instrument = args.instrument.upper()
    groups: dict[dt.date, list[Path]] = {}
    for path in (RAW_ROOT / instrument).glob("**/*h_ticks.bi5"):
        if path.stat().st_size:
            groups.setdefault(hour_from_path(path).date(), []).append(path)
    total_ticks = 0
    published: list[dict[str, object]] = []
    aggregations: dict[str, list[dict[str, object]]] = {resolution: [] for resolution in AGGREGATE_RESOLUTIONS}
    for day, paths in sorted(groups.items()):
        target, count, digest, daily_aggregates = publish_day(instrument, paths, day)
        total_ticks += count
        published.append({
            "path": str(target.relative_to(CURATED_ROOT.parent)), "bytes": target.stat().st_size,
            "rows": count, "sha256": digest, "instrument": instrument, "day": day.isoformat(),
        })
        for resolution, row in daily_aggregates.items():
            aggregations[resolution].append(row)
    partitions = sorted(published, key=lambda row: str(row["day"]))
    identity = hashlib.sha256(json.dumps({"partitions": partitions, "aggregations": aggregations}, sort_keys=True).encode()).hexdigest()[:12]
    version = f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}-{identity}"
    manifest = {
        "dataset_version": version, "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "instrument": instrument, "source": "dukascopy", "schema_version": SCHEMA_VERSION,
        "status": "complete", "release_status": "published", "ticks": total_ticks, "partitions": partitions,
        "aggregations": aggregations,
        "collection": collection_snapshot(instrument, args.requested_start, args.requested_end),
        "coverage_start": min((str(day) for day in groups), default=None),
        "coverage_end": max((str(day) for day in groups), default=None),
    }
    release = RELEASES_ROOT / version
    atomic_json(release / "manifest.json", manifest)
    current = RELEASES_ROOT / "CURRENT"
    current.parent.mkdir(parents=True, exist_ok=True)
    temporary = current.with_suffix(".part")
    temporary.write_text(f"{version}\n", encoding="utf-8")
    os.replace(temporary, current)
    print(json.dumps({"dataset_version": version, "partitions": len(partitions), "ticks": total_ticks}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
