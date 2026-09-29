#!/usr/bin/env python3
"""Exercise the local release, research bundle and safe operational import."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

PROJECTS = Path("/home/codexops/projects")
DATA_ROOT = Path("/home/codexops/lotus-data")
TWO = PROJECTS / "5lotus/python-service"
THREE = PROJECTS / "3lotus/python-service"


def run(command: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, check=True)
    return completed.stdout.strip()


def main() -> int:
    with urllib.request.urlopen("http://127.0.0.1:7773/health", timeout=5) as response:
        assert json.load(response)["status"] == "ok"
    version = (DATA_ROOT / "releases/CURRENT").read_text(encoding="utf-8").strip()
    run([str(TWO / ".venv/bin/python"), "scripts/inspect_local_dataset.py", "--verify-hashes"], TWO)
    with tempfile.TemporaryDirectory(prefix="three-lotus-flow-") as directory:
        temporary = Path(directory)
        bundle_json = run([
            str(TWO / ".venv/bin/python"), "scripts/build_strategy_bundle.py",
            "--strategy-id", "bot-21", "--deployment-id", "integration-shadow",
            "--version", dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "--output", str(temporary / "bundles"), "--approve",
        ], TWO)
        bundle = Path(json.loads(bundle_json.splitlines()[-1])["bundle"])
        environment = os.environ.copy()
        environment["LOTUS_STRATEGY_REGISTRY_PATH"] = str(temporary / "registry")
        receipt_json = run([
            str(THREE / ".venv/bin/python"), "../scripts/import_strategy_bundle.py", "--bundle", str(bundle),
        ], THREE, env=environment)
        receipt = json.loads(receipt_json)
        assert receipt["dataset_version"] == version
        assert receipt["active"] is False and receipt["live_canary_armed"] is False
    print(json.dumps({"status": "ok", "dataset_version": version, "promotion": "inactive-shadow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
