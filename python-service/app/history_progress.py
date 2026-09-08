"""Read-only progress reporting for the shared Dukascopy collection."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


TERMINAL_STATUSES = ("downloaded", "existing", "missing")
DEFAULT_COLLECTION_START = date(2003, 5, 5)


def _hours_in_year(year: int, start: date, end: date) -> int:
    first = max(start, date(year, 1, 1))
    last = min(end, date(year, 12, 31))
    return max(0, (last - first).days + 1) * 24


def load_dukascopy_progress(data_root: Path, instrument: str = "XAUUSD") -> dict[str, object]:
    manifest = data_root / "manifests" / "dukascopy.sqlite3"
    now = datetime.now(timezone.utc)
    empty = {
        "instrument": instrument, "available": False, "running": False,
        "requested_start": None, "requested_end": None, "progress_pct": 0.0,
        "completed_hours": 0, "expected_hours": 0, "pending_hours": 0,
        "equivalent_years": 0.0, "complete_years": 0, "total_years": 0,
        "updated_at": None, "rate_hours_per_minute": 0.0, "eta_seconds": None,
        "years": [],
    }
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
