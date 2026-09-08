"""Read Dukascopy BI5 ticks and aggregate canonical OHLCV windows."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import datetime as dt
import lzma
from pathlib import Path
import struct
from threading import Lock
from typing import Iterable, Literal

RECORD = struct.Struct(">IIIff")
PRICE_SCALE = 1_000
UTC = dt.timezone.utc

RESOLUTION_SECONDS = {
    "1s": 1,
    "5s": 5,
    "15s": 15,
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1_800,
    "1h": 3_600,
    "4h": 14_400,
    "1d": 86_400,
}


@dataclass(frozen=True, slots=True)
class Tick:
    timestamp_ms: int
    bid: float
    ask: float
    bid_volume: float
    ask_volume: float


class TickFileCache:
    """Small thread-safe LRU; it avoids decoding the same visible hours repeatedly."""

    def __init__(self, max_files: int = 48):
        self.max_files = max_files
        self._items: OrderedDict[tuple[str, int, int], tuple[Tick, ...]] = OrderedDict()
        self._lock = Lock()

    def get(self, path: Path, hour_ms: int) -> tuple[Tick, ...]:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        ticks = tuple(decode_bi5(path, hour_ms))
        with self._lock:
            self._items[key] = ticks
            self._items.move_to_end(key)
            while len(self._items) > self.max_files:
                self._items.popitem(last=False)
        return ticks


def hour_from_path(path: Path) -> dt.datetime:
    hour = int(path.name[:2])
    day, month, year = int(path.parent.name), int(path.parent.parent.name), int(path.parent.parent.parent.name)
    return dt.datetime(year, month, day, hour, tzinfo=UTC)


def decode_bi5(path: Path, hour_ms: int | None = None) -> Iterable[Tick]:
    """Decode Dukascopy XAUUSD: ms offset, ask, bid, ask volume, bid volume."""
    if path.stat().st_size == 0:
        return
    if hour_ms is None:
        hour_ms = int(hour_from_path(path).timestamp() * 1_000)
    raw = lzma.decompress(path.read_bytes())
    if len(raw) % RECORD.size:
        raise ValueError(f"invalid BI5 record length in {path}")
    for offset, ask_raw, bid_raw, ask_volume, bid_volume in RECORD.iter_unpack(raw):
        if offset >= 3_600_000:
            continue
        yield Tick(
            timestamp_ms=hour_ms + offset,
            bid=bid_raw / PRICE_SCALE,
            ask=ask_raw / PRICE_SCALE,
            bid_volume=float(bid_volume),
            ask_volume=float(ask_volume),
        )


def choose_resolution(from_ms: int, to_ms: int, viewport_px: int, requested: str) -> str:
    if requested != "auto":
        if requested == "tick" or requested in RESOLUTION_SECONDS:
            return requested
        raise ValueError("unsupported resolution")
    span_seconds = max(1, (to_ms - from_ms) / 1_000)
    target = span_seconds / max(320, min(viewport_px, 4_000))
    for name, seconds in RESOLUTION_SECONDS.items():
        if seconds >= target:
            return name
    return "1d"


def aggregate_ticks(ticks: Iterable[Tick], resolution: str, price_type: Literal["mid", "bid", "ask"]):
    seconds = RESOLUTION_SECONDS[resolution]
    bucket_ms = seconds * 1_000
    output: list[dict] = []
    current: dict | None = None
    spread_sum = 0.0
    for tick in ticks:
        price = tick.bid if price_type == "bid" else tick.ask if price_type == "ask" else (tick.bid + tick.ask) / 2
        bucket = tick.timestamp_ms // bucket_ms * bucket_ms
        spread = tick.ask - tick.bid
        if current is None or current["t"] != bucket:
            if current is not None:
                current["spread_mean"] = spread_sum / current["tick_count"]
                output.append(current)
            spread_sum = spread
            current = {
                "t": bucket, "o": price, "h": price, "l": price, "c": price,
                "bid_volume": tick.bid_volume, "ask_volume": tick.ask_volume,
                "tick_count": 1, "spread_open": spread, "spread_high": spread,
                "spread_low": spread, "spread_close": spread,
            }
        else:
            current["h"] = max(current["h"], price)
            current["l"] = min(current["l"], price)
            current["c"] = price
            current["bid_volume"] += tick.bid_volume
            current["ask_volume"] += tick.ask_volume
            current["tick_count"] += 1
            current["spread_high"] = max(current["spread_high"], spread)
            current["spread_low"] = min(current["spread_low"], spread)
            current["spread_close"] = spread
            spread_sum += spread
    if current is not None:
        current["spread_mean"] = spread_sum / current["tick_count"]
        output.append(current)
    return output


def serialize_ticks(ticks: Iterable[Tick], limit: int = 50_000):
    rows = []
    truncated = False
    for tick in ticks:
        row = {
            "t": tick.timestamp_ms, "bid": tick.bid, "ask": tick.ask,
            "mid": (tick.bid + tick.ask) / 2, "bid_volume": tick.bid_volume,
            "ask_volume": tick.ask_volume, "spread": tick.ask - tick.bid,
        }
        # Lightweight Charts requires a strictly increasing horizontal scale.
        # Dukascopy can emit multiple quotes in one millisecond, so keep the
        # last quote and combine its volumes for that display coordinate.
        if rows and rows[-1]["t"] == tick.timestamp_ms:
            row["bid_volume"] += rows[-1]["bid_volume"]
            row["ask_volume"] += rows[-1]["ask_volume"]
            rows[-1] = row
            continue
        if len(rows) >= limit:
            truncated = True
            break
        rows.append(row)
    return rows, truncated
