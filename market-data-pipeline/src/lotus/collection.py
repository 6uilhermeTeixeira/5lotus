"""Collection progress and throughput metrics shared by CLI and API."""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

TERMINAL_STATUSES = ("downloaded", "existing", "missing")


def progress_snapshot(
    manifest: Path,
    instrument: str,
    requested_start: dt.date,
    requested_end: dt.date,
    *,
    now: dt.datetime | None = None,
) -> dict[str, object]:
    expected = max(0, ((requested_end - requested_start).days + 1) * 24)
    result: dict[str, object] = {
        "requested_start": requested_start.isoformat(), "requested_end": requested_end.isoformat(),
        "expected_hours": expected, "terminal_hours": 0, "attempted_hours": 0,
        "pending_hours": expected, "progress_pct": 0.0, "statuses": {},
        "rate_hours_per_minute_15m": 0.0, "rate_hours_per_minute_60m": 0.0,
        "eta_seconds": None, "updated_at": None,
    }
    if not manifest.exists():
        return result
    now = now or dt.datetime.now(dt.timezone.utc)
    database = sqlite3.connect(f"file:{manifest}?mode=ro", uri=True)
    counts = dict(database.execute(
        "SELECT status,count(*) FROM downloads WHERE instrument=? GROUP BY status", (instrument,)
    ))
    updated = database.execute(
        "SELECT max(updated_at) FROM downloads WHERE instrument=?", (instrument,)
    ).fetchone()[0]
    rates: dict[int, float] = {}
    for minutes in (15, 60):
        cutoff = (now - dt.timedelta(minutes=minutes)).isoformat()
        recent = database.execute(
            "SELECT count(*) FROM downloads WHERE instrument=? AND status IN (?,?,?) AND updated_at>=?",
            (instrument, *TERMINAL_STATUSES, cutoff),
        ).fetchone()[0]
        rates[minutes] = recent / minutes
    database.close()
    terminal = sum(counts.get(status, 0) for status in TERMINAL_STATUSES)
    pending = max(0, expected - terminal)
    rate = rates[15] or rates[60]
    result.update({
        "terminal_hours": terminal, "attempted_hours": sum(counts.values()), "pending_hours": pending,
        "progress_pct": round(min(100.0, terminal * 100 / expected), 4) if expected else 100.0,
        "statuses": counts, "rate_hours_per_minute_15m": round(rates[15], 3),
        "rate_hours_per_minute_60m": round(rates[60], 3),
        "eta_seconds": round(pending / rate * 60) if rate else None, "updated_at": updated,
    })
    return result
