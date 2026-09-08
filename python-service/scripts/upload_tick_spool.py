"""Upload closed MT5 tick spool files without blocking the EA event loop."""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SPOOL_ROOT = Path(os.getenv("DAYTRADE_TICK_SPOOL_ROOT", "/data/mt5-prefix"))
API_URL = os.getenv("DAYTRADE_TICK_API_URL", "http://127.0.0.1:1112/api/ticks")
INGEST_KEY = os.getenv("DAYTRADE_INGEST_API_KEY", "")
BATCH_SIZE = 1000
POLL_SECONDS = float(os.getenv("DAYTRADE_TICK_UPLOAD_POLL_SECONDS", "2"))
FORWARD_COLLECTOR_ID = os.getenv("DAYTRADE_TICK_FORWARD_COLLECTOR_ID", "2lotus-forward-01")


def find_ready_files() -> list[Path]:
    return sorted(
        SPOOL_ROOT.glob(f"**/2lotus-ticks/{FORWARD_COLLECTOR_ID}/*.ready.csv"),
        key=lambda path: path.stat().st_mtime,
    )


def read_ticks(path: Path) -> tuple[float, list[dict[str, int | float]]]:
    with path.open(newline="", encoding="ascii") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        return 0.0, []
    ticks = [
        {
            "time_msc": int(row["time_msc"]),
            "sequence": int(row["sequence"]),
            "bid": float(row["bid"]),
            "ask": float(row["ask"]),
            "last": float(row["last"]),
            "volume": int(row["volume"]),
            "volume_real": float(row["volume_real"]),
            "flags": int(row["flags"]),
        }
        for row in rows
    ]
    point_sizes = {float(row["point_size"]) for row in rows}
    if len(point_sizes) != 1 or next(iter(point_sizes), 0) <= 0:
        raise ValueError("tick spool must contain one positive point_size")
    return point_sizes.pop(), ticks


def upload_file(path: Path) -> None:
    if path.parent.name != FORWARD_COLLECTOR_ID:
        raise ValueError(f"unexpected tick collector: {path.parent.name}")
    point_size, ticks = read_ticks(path)
    if not ticks:
        path.unlink()
        return
    collector_id = path.parent.name
    symbol = path.name.split("-", 1)[0]
    for start in range(0, len(ticks), BATCH_SIZE):
        payload = json.dumps(
            {
                "collector_id": collector_id,
                "symbol": symbol,
                "point_size": point_size,
                "ticks": ticks[start:start + BATCH_SIZE],
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            API_URL,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "X-2Lotus-Ingest-Key": INGEST_KEY},
        )
        with urlopen(request, timeout=15) as response:
            if response.status != 204:
                raise RuntimeError(f"unexpected tick ingest status: {response.status}")
    path.unlink()


def run() -> None:
    if not INGEST_KEY:
        raise RuntimeError("DAYTRADE_INGEST_API_KEY is required")
    while True:
        for path in find_ready_files():
            try:
                upload_file(path)
            except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
                print(json.dumps({"event": "tick_spool_upload_failed", "file": str(path), "error": str(error)}), flush=True)
                break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
