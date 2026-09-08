"""Stable filesystem locations shared by the Lotus applications."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.getenv("LOTUS_DATA_ROOT", "/home/codexops/lotus-data")).expanduser().resolve()
RAW_ROOT = DATA_ROOT / "raw" / "dukascopy"
MANIFEST_ROOT = DATA_ROOT / "manifests"
CURATED_ROOT = DATA_ROOT / "curated"
DERIVED_ROOT = DATA_ROOT / "derived"
RELEASES_ROOT = DATA_ROOT / "releases"

