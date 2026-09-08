import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from app.local_dataset import DatasetError, DatasetRelease


class LocalDatasetTest(unittest.TestCase):
    def make_release(self, root: Path, *, status: str = "complete", schema: str = "xauusd-ticks-v1") -> Path:
        version = "20260902T000000Z-test"
        partition = root / "curated/ticks/sample.parquet"
        partition.parent.mkdir(parents=True)
        partition.write_bytes(b"parquet-test")
        release = root / "releases" / version
        release.mkdir(parents=True)
        (root / "releases/CURRENT").write_text(version + "\n")
        manifest = {"dataset_version": version, "status": status, "schema_version": schema, "partitions": [{"path": "curated/ticks/sample.parquet", "sha256": hashlib.sha256(b"parquet-test").hexdigest()}]}
        (release / "manifest.json").write_text(json.dumps(manifest))
        return partition

    def test_pins_current_and_validates_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_release(root)
            release = DatasetRelease.open(root)
            self.assertEqual(release.version, "20260902T000000Z-test")
            self.assertEqual(len(release.partitions(verify_hashes=True)), 1)

    def test_rejects_provisional_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_release(root, status="provisional")
            with self.assertRaises(DatasetError):
                DatasetRelease.open(root)

    def test_rejects_tampered_partition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            partition = self.make_release(root)
            partition.write_bytes(b"tampered")
            with self.assertRaises(DatasetError):
                DatasetRelease.open(root).partitions(verify_hashes=True)

