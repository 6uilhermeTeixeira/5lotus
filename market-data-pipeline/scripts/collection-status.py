#!/usr/bin/env python3
"""Print a compact summary of the Dukascopy collection manifest."""

import datetime as dt
import sqlite3
from pathlib import Path
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lotus.collection import progress_snapshot  # noqa: E402

manifest = Path(os.getenv("LOTUS_DATA_ROOT", "/home/codexops/lotus-data")) / "manifests/dukascopy.sqlite3"
if not manifest.exists():
    raise SystemExit("manifest not created yet")
db = sqlite3.connect(manifest)
for row in db.execute("SELECT status, count(*), coalesce(sum(bytes),0), coalesce(sum(records),0) FROM downloads GROUP BY status ORDER BY status"):
    print(f"{row[0]:10} files={row[1]:7} bytes={row[2]:12} ticks={row[3]:12}")
row = db.execute("SELECT min(hour_utc), max(hour_utc), max(updated_at) FROM downloads WHERE status IN ('downloaded','existing')").fetchone()
print(f"coverage={row[0]} .. {row[1]} updated={row[2]}")
start = dt.date.fromisoformat(os.getenv("LOTUS_COLLECTION_START", "2003-05-05"))
end = dt.date.fromisoformat(os.getenv("LOTUS_COLLECTION_END", str(dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))))
progress = progress_snapshot(manifest, "XAUUSD", start, end)
eta = progress["eta_seconds"]
eta_text = "unknown" if eta is None else str(dt.timedelta(seconds=int(eta)))
print(
    f"progress={progress['terminal_hours']}/{progress['expected_hours']} "
    f"({progress['progress_pct']:.4f}%) pending={progress['pending_hours']} "
    f"rate15m={progress['rate_hours_per_minute_15m']:.3f}h/min eta={eta_text}"
)
