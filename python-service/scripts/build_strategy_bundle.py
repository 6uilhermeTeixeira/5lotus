#!/usr/bin/env python3
"""Build a manually approved, immutable strategy promotion bundle for 3lotus."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))

from app.local_dataset import DatasetRelease  # noqa: E402
STRATEGY_FILES = (
    "strategy.py", "indicators.py", "regime.py", "adaptive.py", "schemas.py", "config.py",
    "strategies/__init__.py", "strategies/core.py", "strategies/tick.py",
    "strategies/portfolio.py", "strategies/router.py",
)
CONTRACT_VERSION = "lotus-strategy-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--data-root", type=Path, default=Path(os.getenv("LOTUS_DATA_ROOT", "/home/codexops/lotus-data")))
    parser.add_argument("--dataset-version", default=os.getenv("LOTUS_DATASET_VERSION", "CURRENT"))
    parser.add_argument("--output", type=Path, default=REPOSITORY_ROOT / ".runtime/promotions")
    parser.add_argument("--approve", action="store_true", help="required human approval gate")
    args = parser.parse_args()
    if not args.approve:
        parser.error("--approve is required; bundles are never promoted automatically")
    catalog = json.loads((SERVICE_ROOT / "data/bots.json").read_text(encoding="utf-8"))
    bot = next((row for row in catalog if row.get("id") == args.strategy_id), None)
    if bot is None:
        raise SystemExit(f"unknown strategy: {args.strategy_id}")
    dataset = DatasetRelease.open(args.data_root, args.dataset_version)
    subprocess.run(
        [os.fspath(SERVICE_ROOT / ".venv/bin/python"), "-m", "unittest", "discover", "-s", "tests"],
        cwd=SERVICE_ROOT, check=True,
    )
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True).strip()
    files = {name: {"sha256": digest(SERVICE_ROOT / "app" / name)} for name in STRATEGY_FILES}
    fingerprint_payload = {"bot": bot, "files": files, "dataset_version": dataset.version}
    manifest = {
        "contract": CONTRACT_VERSION,
        "strategy_id": args.strategy_id,
        "deployment_id": args.deployment_id,
        "version": args.version,
        "source_commit": source_commit,
        "dataset_version": dataset.version,
        "config_fingerprint": hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest(),
        "approved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "approved_by": os.getenv("USER", "unknown"),
        "tests": "python -m unittest discover -s tests",
        "files": files,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / f"{args.deployment_id}-{args.version}.tar.gz"
    with tempfile.TemporaryDirectory() as directory:
        temporary_root = Path(directory)
        manifest_path = temporary_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with tarfile.open(target, "w:gz") as archive:
            archive.add(manifest_path, arcname="manifest.json")
            for name in STRATEGY_FILES:
                archive.add(SERVICE_ROOT / "app" / name, arcname=f"source/{name}")
    print(json.dumps({"bundle": str(target), "sha256": digest(target), "strategy_id": args.strategy_id, "dataset_version": dataset.version}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
