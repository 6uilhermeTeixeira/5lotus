import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lotus.collection import progress_snapshot
from lotus.ingestion.dukascopy import connect_manifest


class CollectionProgressTests(unittest.TestCase):
    def test_reports_terminal_rate_and_eta(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "downloads.sqlite3"
            database = connect_manifest(manifest)
            now = dt.datetime(2026, 9, 2, tzinfo=dt.timezone.utc)
            for hour, status, minutes_ago in ((0, "downloaded", 5), (1, "missing", 10), (2, "retry", 2)):
                database.execute(
                    """INSERT INTO downloads
                       (instrument,hour_utc,remote_path,status,attempts,updated_at)
                       VALUES (?,?,?,?,?,?)""",
                    ("XAUUSD", f"2026-09-01T{hour:02d}:00:00+00:00", "remote", status, 1,
                     (now - dt.timedelta(minutes=minutes_ago)).isoformat()),
                )
            database.commit()
            database.close()
            snapshot = progress_snapshot(manifest, "XAUUSD", dt.date(2026, 9, 1), dt.date(2026, 9, 1), now=now)
            self.assertEqual(snapshot["expected_hours"], 24)
            self.assertEqual(snapshot["terminal_hours"], 2)
            self.assertEqual(snapshot["attempted_hours"], 3)
            self.assertEqual(snapshot["progress_pct"], 8.3333)
            self.assertGreater(snapshot["rate_hours_per_minute_15m"], 0)
            self.assertIsNotNone(snapshot["eta_seconds"])
