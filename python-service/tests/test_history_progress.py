import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.history_progress import load_dukascopy_progress


class HistoryProgressTests(unittest.TestCase):
    def test_groups_terminal_download_hours_by_year(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifests" / "dukascopy.sqlite3"
            manifest.parent.mkdir()
            database = sqlite3.connect(manifest)
            database.execute("""CREATE TABLE downloads (
                instrument TEXT, hour_utc TEXT, status TEXT, updated_at TEXT
            )""")
            now = datetime.now(timezone.utc).isoformat()
            database.executemany(
                "INSERT INTO downloads VALUES (?,?,?,?)",
                [
                    ("XAUUSD", "2003-05-05T00:00:00+00:00", "downloaded", now),
                    ("XAUUSD", "2003-05-05T01:00:00+00:00", "missing", now),
                    ("XAUUSD", "2004-01-01T00:00:00+00:00", "retry", now),
                ],
            )
            database.commit()
            database.close()

            progress = load_dukascopy_progress(root)

            self.assertTrue(progress["available"])
            self.assertTrue(progress["running"])
            self.assertEqual(progress["completed_hours"], 2)
            self.assertEqual(progress["pending_hours"], progress["expected_hours"] - 2)
            self.assertEqual(progress["years"][0]["year"], 2003)
            self.assertEqual(progress["years"][0]["completed_hours"], 2)
            self.assertEqual(progress["years"][1]["retries"], 1)

    def test_missing_manifest_returns_available_false(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            progress = load_dukascopy_progress(Path(directory))

        self.assertFalse(progress["available"])
        self.assertEqual(progress["years"], [])
