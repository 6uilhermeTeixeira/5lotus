#!/usr/bin/env python3
"""Resumable downloader for Dukascopy's public hourly BI5 tick archive."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import lzma
import os
from pathlib import Path
import random
import sqlite3
import struct
import subprocess
import time
import urllib.error
import urllib.request

from lotus.paths import MANIFEST_ROOT, RAW_ROOT

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
RECORD = struct.Struct(">IIIff")
USER_AGENT = "1lotus-research/0.1 (historical market data; low-rate client)"


def iter_hours(start: dt.date, end: dt.date):
    """Yield UTC hours for an inclusive date range."""
    current = dt.datetime.combine(start, dt.time(), tzinfo=dt.timezone.utc)
    stop = dt.datetime.combine(end + dt.timedelta(days=1), dt.time(), tzinfo=dt.timezone.utc)
    while current < stop:
        yield current
        current += dt.timedelta(hours=1)


def remote_path(instrument: str, hour: dt.datetime) -> str:
    """Dukascopy paths use zero-based month numbers."""
    return (
        f"{instrument}/{hour.year:04d}/{hour.month - 1:02d}/"
        f"{hour.day:02d}/{hour.hour:02d}h_ticks.bi5"
    )


def local_path(root: Path, instrument: str, hour: dt.datetime) -> Path:
    return root / instrument / f"{hour.year:04d}" / f"{hour.month:02d}" / f"{hour.day:02d}" / f"{hour.hour:02d}h_ticks.bi5"


def validate_bi5(payload: bytes) -> tuple[int, int | None, int | None]:
    """Return record count and min/max millisecond offset after integrity checks."""
    if not payload:
        return 0, None, None
    raw = lzma.decompress(payload)
    if len(raw) % RECORD.size:
        raise ValueError(f"decoded size {len(raw)} is not divisible by {RECORD.size}")
    count = len(raw) // RECORD.size
    first_ms = RECORD.unpack_from(raw, 0)[0] if count else None
    last_ms = RECORD.unpack_from(raw, len(raw) - RECORD.size)[0] if count else None
    if first_ms is not None and (first_ms >= 3_600_000 or last_ms >= 3_600_000):
        raise ValueError(f"tick offset outside hour: {first_ms}..{last_ms}")
    return count, first_ms, last_ms


def connect_manifest(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            instrument TEXT NOT NULL,
            hour_utc TEXT NOT NULL,
            remote_path TEXT NOT NULL,
            status TEXT NOT NULL,
            http_status INTEGER,
            attempts INTEGER NOT NULL DEFAULT 0,
            bytes INTEGER,
            records INTEGER,
            sha256 TEXT,
            error TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (instrument, hour_utc)
        )
        """
    )
    db.commit()
    return db


def fetch(url: str, timeout: float) -> tuple[int, bytes]:
    # curl is used because this sandbox's network proxy intermittently refuses
    # Python urllib connections to the Dukascopy CDN while curl can reconnect.
    marker = b"\n1LOTUS_HTTP_STATUS:"
    process = subprocess.run(
        ["curl", "-4", "-sS", "-L", "--connect-timeout", "10", "--max-time", str(int(timeout)),
         "-A", USER_AGENT, "-w", "\n1LOTUS_HTTP_STATUS:%{http_code}", url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    body, separator, status_bytes = process.stdout.rpartition(marker)
    if not separator:
        raise OSError(process.stderr.decode("utf-8", "replace").strip() or f"curl exit {process.returncode}")
    status = int(status_bytes)
    if status in (404, 410):
        return status, b""
    if status != 200:
        raise urllib.error.HTTPError(url, status, f"HTTP {status}", None, None)
    if process.returncode:
        raise OSError(process.stderr.decode("utf-8", "replace").strip() or f"curl exit {process.returncode}")
    return status, body


def download_one(
    instrument: str,
    hour: dt.datetime,
    raw_root: Path,
    retries: int,
    timeout: float,
) -> dict:
    relative = remote_path(instrument, hour)
    target = local_path(raw_root, instrument, hour)
    if target.is_file() and target.stat().st_size:
        payload = target.read_bytes()
        records, _, _ = validate_bi5(payload)
        return {"status": "existing", "http": 200, "attempts": 0, "bytes": len(payload), "records": records,
                "sha256": hashlib.sha256(payload).hexdigest(), "error": None, "relative": relative}

    last_error = None
    last_http = None
    for attempt in range(1, retries + 1):
        try:
            status, payload = fetch(f"{BASE_URL}/{relative}", timeout)
            last_http = status
            if status in (404, 410):
                return {"status": "missing", "http": status, "attempts": attempt, "bytes": 0, "records": 0,
                        "sha256": None, "error": None, "relative": relative}
            records, _, _ = validate_bi5(payload)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + f".{os.getpid()}.part")
            temporary.write_bytes(payload)
            os.replace(temporary, target)
            return {"status": "downloaded", "http": status, "attempts": attempt, "bytes": len(payload),
                    "records": records, "sha256": hashlib.sha256(payload).hexdigest(), "error": None,
                    "relative": relative}
        except urllib.error.HTTPError as exc:
            last_http, last_error = exc.code, f"HTTP {exc.code}"
        except Exception as exc:  # network and validation failures are retryable
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            time.sleep(min(30.0, 1.8 ** attempt) + random.random())
    return {"status": "retry", "http": last_http, "attempts": retries, "bytes": 0, "records": 0,
            "sha256": None, "error": last_error, "relative": relative}


def already_done(db: sqlite3.Connection, instrument: str, hour: dt.datetime) -> bool:
    row = db.execute(
        "SELECT status FROM downloads WHERE instrument=? AND hour_utc=?",
        (instrument, hour.isoformat()),
    ).fetchone()
    return bool(row and row[0] in ("downloaded", "existing", "missing"))


def save_result(db: sqlite3.Connection, instrument: str, hour: dt.datetime, result: dict) -> None:
    db.execute(
        """
        INSERT INTO downloads
        (instrument, hour_utc, remote_path, status, http_status, attempts, bytes, records, sha256, error, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(instrument, hour_utc) DO UPDATE SET
          status=excluded.status, http_status=excluded.http_status, attempts=downloads.attempts+excluded.attempts,
          bytes=excluded.bytes, records=excluded.records, sha256=excluded.sha256,
          error=excluded.error, updated_at=excluded.updated_at
        """,
        (instrument, hour.isoformat(), result["relative"], result["status"], result["http"], result["attempts"],
         result["bytes"], result["records"], result["sha256"], result["error"], dt.datetime.now(dt.timezone.utc).isoformat()),
    )
    db.commit()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def workers_for_batch(initial: int, maximum: int, batch_number: int) -> int:
    """Increase concurrency by one after each completed batch, up to maximum."""
    return min(maximum, initial + batch_number)


def main() -> int:
    yesterday = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument", default="XAUUSD")
    parser.add_argument("--start", type=parse_date, default=dt.date(2003, 5, 5))
    parser.add_argument("--end", type=parse_date, default=yesterday)
    parser.add_argument("--workers", type=int, default=2, help="maximum concurrent downloads")
    parser.add_argument(
        "--initial-workers",
        type=int,
        help="starting concurrency; increases by one after each 96-hour batch",
    )
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_ROOT / "dukascopy.sqlite3")
    parser.add_argument("--newest-first", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must not be after --end")
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    initial_workers = args.initial_workers if args.initial_workers is not None else args.workers
    if not 1 <= initial_workers <= args.workers:
        parser.error("--initial-workers must be between 1 and --workers")

    instrument = args.instrument.upper()
    db = connect_manifest(args.manifest)
    hours = [h for h in iter_hours(args.start, args.end) if not already_done(db, instrument, h)]
    if args.newest_first:
        hours.reverse()
    print(
        f"planned={len(hours)} instrument={instrument} range={args.start}..{args.end} "
        f"workers={initial_workers}->{args.workers}",
        flush=True,
    )

    totals = {"downloaded": 0, "existing": 0, "missing": 0, "retry": 0}
    completed = 0
    try:
        # A fresh pool per bounded batch lets concurrency ramp without queuing the
        # multi-decade collection in memory. Completed results remain resumable.
        for batch_number, offset in enumerate(range(0, len(hours), 96)):
            batch = hours[offset:offset + 96]
            active_workers = workers_for_batch(initial_workers, args.workers, batch_number)
            print(
                f"batch={batch_number + 1} hours={len(batch)} workers={active_workers}",
                flush=True,
            )
            with concurrent.futures.ThreadPoolExecutor(max_workers=active_workers) as pool:
                futures = {pool.submit(download_one, instrument, h, args.raw_root, args.retries, args.timeout): h for h in batch}
                for future in concurrent.futures.as_completed(futures):
                    hour = futures[future]
                    result = future.result()
                    save_result(db, instrument, hour, result)
                    totals[result["status"]] += 1
                    completed += 1
                    print(f"{hour.isoformat()} {result['status']} bytes={result['bytes']} records={result['records']}"
                          + (f" error={result['error']}" if result["error"] else ""), flush=True)
                    if completed % 100 == 0:
                        print(f"progress={completed}/{len(hours)} totals={totals}", flush=True)
    except KeyboardInterrupt:
        print("interrupted; completed entries are safely recorded", flush=True)
        pool.shutdown(wait=False, cancel_futures=True)
        return 130
    print(f"complete totals={totals}", flush=True)
    return 0 if totals["retry"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
