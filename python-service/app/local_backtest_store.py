"""Atomic local storage for compact backtest snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .schemas import HistoricalReplayResponse


def snapshot_path(root: Path, bot_id: str, period_days: int) -> Path:
    if not bot_id.replace("-", "").isalnum():
        raise ValueError("invalid bot id")
    return root / f"{bot_id}-{period_days}.json"


def save_local_backtest(root: Path, replay: HistoricalReplayResponse, period_days: int) -> None:
    target = snapshot_path(root, replay.bot_id, period_days)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = replay.model_dump(mode="json")
    payload["candles"] = []
    handle, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".part", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as temporary:
            json.dump(payload, temporary, ensure_ascii=False, separators=(",", ":"))
            temporary.write("\n")
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def load_local_backtest(root: Path, bot_id: str, period_days: int) -> HistoricalReplayResponse | None:
    target = snapshot_path(root, bot_id, period_days)
    if not target.is_file():
        return None
    return HistoricalReplayResponse.model_validate_json(target.read_text(encoding="utf-8"))
