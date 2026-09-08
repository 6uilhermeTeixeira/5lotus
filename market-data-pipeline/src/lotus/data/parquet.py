"""Read the immutable CURRENT release without touching raw BI5 files."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Iterator

import duckdb

from lotus.data.market import Tick
from lotus.paths import DATA_ROOT, RELEASES_ROOT


class ParquetReleaseReader:
    def __init__(self) -> None:
        self._lock = Lock()
        self._version: str | None = None
        self._files: tuple[str, ...] = ()
        self._aggregates: dict[str, tuple[str, ...]] = {}

    def _current_files(self, instrument: str) -> tuple[str, ...]:
        pointer = RELEASES_ROOT / "CURRENT"
        if not pointer.is_file():
            return ()
        version = pointer.read_text(encoding="utf-8").strip()
        with self._lock:
            if self._version == version:
                return self._files
            manifest_path = RELEASES_ROOT / version / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files: list[str] = []
            for partition in manifest.get("partitions", []):
                if partition.get("instrument", manifest.get("instrument")) != instrument:
                    continue
                path = (DATA_ROOT / partition["path"]).resolve()
                if not path.is_relative_to(DATA_ROOT) or not path.is_file():
                    raise RuntimeError(f"invalid release partition: {partition.get('path')}")
                files.append(str(path))
            aggregates: dict[str, tuple[str, ...]] = {}
            for resolution, entries in manifest.get("aggregations", {}).items():
                paths = []
                for entry in entries:
                    path = (DATA_ROOT / entry["path"]).resolve()
                    if not path.is_relative_to(DATA_ROOT) or not path.is_file():
                        raise RuntimeError(f"invalid aggregate partition: {entry.get('path')}")
                    paths.append(str(path))
                aggregates[resolution] = tuple(paths)
            self._version, self._files, self._aggregates = version, tuple(files), aggregates
            return self._files

    def ticks(self, instrument: str, from_ms: int, to_ms: int) -> Iterator[Tick]:
        files = self._current_files(instrument)
        if not files:
            return
        connection = duckdb.connect(":memory:")
        try:
            cursor = connection.execute(
                """SELECT timestamp_ms,bid,ask,bid_volume,ask_volume
                   FROM read_parquet(?, union_by_name=true)
                   WHERE timestamp_ms>=? AND timestamp_ms<? ORDER BY timestamp_ms""",
                [list(files), from_ms, to_ms],
            )
            while rows := cursor.fetchmany(50_000):
                for row in rows:
                    yield Tick(*row)
        finally:
            connection.close()

    def candles(self, instrument: str, resolution: str, from_ms: int, to_ms: int) -> list[dict[str, object]] | None:
        self._current_files(instrument)
        files = self._aggregates.get(resolution)
        if not files:
            return None
        connection = duckdb.connect(":memory:")
        try:
            cursor = connection.execute(
                """SELECT t,o,h,l,c,bid_volume,ask_volume,tick_count,
                          spread_open,spread_high,spread_low,spread_close,spread_mean
                   FROM read_parquet(?, union_by_name=true)
                   WHERE t>=? AND t<? ORDER BY t LIMIT 5001""",
                [list(files), from_ms, to_ms],
            )
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            connection.close()

    @property
    def version(self) -> str | None:
        return self._version
