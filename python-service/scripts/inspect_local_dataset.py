#!/usr/bin/env python3
"""Validate and summarize the dataset release pinned from 1lotus."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.local_dataset import DatasetRelease  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/home/codexops/lotus-data"))
    parser.add_argument("--version", default="CURRENT")
    parser.add_argument("--verify-hashes", action="store_true")
    args = parser.parse_args()
    release = DatasetRelease.open(args.root, args.version)
    partitions = release.partitions(verify_hashes=args.verify_hashes)
    print(f"version={release.version} schema={release.manifest['schema_version']} partitions={len(partitions)} ticks={release.manifest.get('ticks', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
