"""Read-only progress reporting for the shared Dukascopy collection."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


TERMINAL_STATUSES = ("downloaded", "existing", "missing")
DEFAULT_COLLECTION_START = date(2003, 5, 5)
FUSION_FILE_PATTERN = re.compile(r"^(?P<symbol>[A-Za-z0-9._-]+)-history-(?P<start>\d+)-(?P<end>\d+)\.(?:ready\.csv|empty\.txt)$")


def _hours_in_year(year: int, start: date, end: date) -> int:
    first = max(start, date(year, 1, 1))
    last = min(end, date(year, 12, 31))
    return max(0, (last - first).days + 1) * 24


def _empty_progress(instrument: str) -> dict[str, object]:
    return {
        "instrument": instrument, "available": False, "running": False,
        "requested_start": None, "requested_end": None, "progress_pct": 0.0,
        "completed_hours": 0, "expected_hours": 0, "pending_hours": 0,
        "equivalent_years": 0.0, "complete_years": 0, "total_years": 0,
        "updated_at": None, "rate_hours_per_minute": 0.0, "eta_seconds": None,
        "years": [],
    }


def load_dukascopy_progress(data_root: Path, instrument: str = "XAUUSD") -> dict[str, object]:
    manifest = data_root / "manifests" / "dukascopy.sqlite3"
    now = datetime.now(timezone.utc)
    empty = _empty_progress(instrument)
    if not manifest.is_file():
        return empty

    database = sqlite3.connect(f"file:{manifest}?mode=ro", uri=True, timeout=2)
    try:
        latest = database.execute(
            "SELECT max(hour_utc), max(updated_at) FROM downloads WHERE instrument=?",
            (instrument,),
        ).fetchone()
        if not latest or not latest[0]:
            return {**empty, "available": True}
        requested_start = DEFAULT_COLLECTION_START
        requested_end = date.fromisoformat(latest[0][:10])
        rows = database.execute(
            """SELECT substr(hour_utc,1,4) AS year, status, count(*)
               FROM downloads WHERE instrument=? GROUP BY year,status ORDER BY year""",
            (instrument,),
        ).fetchall()
        cutoff = (now - timedelta(minutes=15)).isoformat()
        recent = database.execute(
            """SELECT count(*) FROM downloads
               WHERE instrument=? AND status IN (?,?,?) AND updated_at>=?""",
            (instrument, *TERMINAL_STATUSES, cutoff),
        ).fetchone()[0]
    finally:
        database.close()

    counts: dict[int, dict[str, int]] = {}
    for year_text, status, count in rows:
        counts.setdefault(int(year_text), {})[status] = count
    years = []
    completed_total = 0
    complete_years = 0
    for year in range(requested_start.year, requested_end.year + 1):
        statuses = counts.get(year, {})
        completed = sum(statuses.get(status, 0) for status in TERMINAL_STATUSES)
        expected = _hours_in_year(year, requested_start, requested_end)
        progress = min(100.0, completed * 100 / expected) if expected else 100.0
        complete = completed >= expected
        completed_total += completed
        complete_years += int(complete)
        years.append({
            "year": year, "completed_hours": completed, "expected_hours": expected,
            "pending_hours": max(0, expected - completed), "progress_pct": round(progress, 2),
            "complete": complete, "retries": statuses.get("retry", 0),
        })

    expected_total = sum(item["expected_hours"] for item in years)
    pending = max(0, expected_total - completed_total)
    rate = recent / 15
    updated = datetime.fromisoformat(latest[1]) if latest[1] else None
    if updated and updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    running = bool(updated and now - updated <= timedelta(minutes=5) and pending)
    return {
        "instrument": instrument, "available": True, "running": running,
        "requested_start": requested_start.isoformat(), "requested_end": requested_end.isoformat(),
        "progress_pct": round(min(100.0, completed_total * 100 / expected_total), 2),
        "completed_hours": completed_total, "expected_hours": expected_total, "pending_hours": pending,
        "equivalent_years": round(completed_total / (365.2425 * 24), 2),
        "complete_years": complete_years, "total_years": len(years),
        "updated_at": updated.isoformat() if updated else None,
        "rate_hours_per_minute": round(rate, 2),
        "eta_seconds": round(pending / rate * 60) if rate else None,
        "years": years,
    }


def _read_state(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator and value.strip().isdigit():
            values[key.strip()] = int(value.strip())
    return values


def load_fusion_progress(spool_root: Path, collector_id: str, instrument: str = "XAUUSD") -> dict[str, object]:
    """Report the coverage exported by the MT5 Fusion history collector.

    Both tick files and explicit empty-hour markers count as completed.  This
    keeps the progress durable across MT5 restarts, rather than trusting only
    its current in-memory export checkpoint.
    """
    empty = _empty_progress(instrument)
    collector = spool_root / "2lotus-ticks" / collector_id
    state_path = collector / "history-state.txt"
    state = _read_state(state_path)
    ranges: list[tuple[int, int, float]] = []
    if collector.is_dir():
        for item in collector.iterdir():
            match = FUSION_FILE_PATTERN.match(item.name)
            if not match or match.group("symbol").upper() != instrument.upper():
                continue
            start, end = int(match.group("start")), int(match.group("end"))
            if end > start:
                ranges.append((start, end, item.stat().st_mtime))

    state_start = state.get("start_msc")
    state_end = state.get("end_msc")
    if not ranges and not (state_start and state_end and state_end > state_start):
        return empty

    latest_end = max([end for _, end, _ in ranges] + ([state_end] if state_end else []))
    requested_end_msc = state_end or latest_end
    requested_start_msc = state_start or requested_end_msc - 365 * 24 * 60 * 60 * 1000
    if requested_end_msc <= requested_start_msc:
        return empty

    expected_hours = (requested_end_msc - requested_start_msc + 3_599_999) // 3_600_000
    completed_hours: set[int] = set()
    for start, end, _ in ranges:
        start = max(start, requested_start_msc)
        end = min(end, requested_end_msc)
        for hour in range(start // 3_600_000, (end + 3_599_999) // 3_600_000):
            completed_hours.add(hour)

    years: list[dict[str, object]] = []
    complete_years = 0
    start_year = datetime.fromtimestamp(requested_start_msc / 1000, tz=timezone.utc).year
    end_year = datetime.fromtimestamp((requested_end_msc - 1) / 1000, tz=timezone.utc).year
    for year in range(start_year, end_year + 1):
        year_start = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        year_end = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        first_hour = max(requested_start_msc, year_start) // 3_600_000
        last_hour = (min(requested_end_msc, year_end) + 3_599_999) // 3_600_000
        expected = max(0, last_hour - first_hour)
        completed = sum(hour in completed_hours for hour in range(first_hour, last_hour))
        progress = min(100.0, completed * 100 / expected) if expected else 100.0
        complete = completed >= expected
        complete_years += int(complete)
        years.append({
            "year": year, "completed_hours": completed, "expected_hours": expected,
            "pending_hours": max(0, expected - completed), "progress_pct": round(progress, 2),
            "complete": complete, "retries": 0,
        })

    updated_candidates = [mtime for _, _, mtime in ranges]
    if state_path.is_file():
        updated_candidates.append(state_path.stat().st_mtime)
    updated = datetime.fromtimestamp(max(updated_candidates), tz=timezone.utc)
    completed = len(completed_hours)
    pending = max(0, expected_hours - completed)
    return {
        "instrument": instrument, "available": True,
        "running": bool(pending and datetime.now(timezone.utc) - updated <= timedelta(minutes=5)),
        "requested_start": datetime.fromtimestamp(requested_start_msc / 1000, tz=timezone.utc).isoformat(),
        "requested_end": datetime.fromtimestamp(requested_end_msc / 1000, tz=timezone.utc).isoformat(),
        "progress_pct": round(min(100.0, completed * 100 / expected_hours), 2),
        "completed_hours": completed, "expected_hours": expected_hours, "pending_hours": pending,
        "equivalent_years": round(completed / (365.2425 * 24), 2),
        "complete_years": complete_years, "total_years": len(years),
        "updated_at": updated.isoformat(), "rate_hours_per_minute": 0.0, "eta_seconds": None,
        "years": years,
    }
