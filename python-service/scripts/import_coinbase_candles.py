"""Import public Coinbase Exchange BTC-USD candles into the canonical store."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import get_settings
from app.schemas import CandleSnapshot
from app.supabase_store import SupabaseStore


COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
GRANULARITY_SECONDS = 300
MAX_CANDLES_PER_REQUEST = 300


def _fetch_chunk(start: datetime, end: datetime) -> list[CandleSnapshot]:
    query = urlencode(
        {
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "granularity": GRANULARITY_SECONDS,
        }
    )
    request = Request(
        f"{COINBASE_CANDLES_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "2Lotus-research/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        rows = json.loads(response.read().decode("utf-8"))
    return [
        CandleSnapshot(
            timestamp_utc=datetime.fromtimestamp(row[0], tz=timezone.utc),
            low=float(row[1]),
            high=float(row[2]),
            open=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--bot-id", default="bot-btc-13")
    args = parser.parse_args()
    if not 1 <= args.days <= 3650:
        parser.error("--days must be between 1 and 3650")

    store = SupabaseStore(get_settings())
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    end -= timedelta(minutes=end.minute % 5)
    start = end - timedelta(days=args.days)
    # Coinbase treats both boundaries as candle buckets, so 299 intervals yield
    # at most 300 returned candles.
    chunk_span = timedelta(seconds=GRANULARITY_SECONDS * (MAX_CANDLES_PER_REQUEST - 1))
    cursor = start
    imported = 0
    while cursor < end:
        chunk_end = min(cursor + chunk_span, end)
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                candles = _fetch_chunk(cursor, chunk_end)
                store.upsert_candles(args.bot_id, "BTCUSD", "M5", candles)
                imported += len(candles)
                print(f"CHUNK start={cursor.isoformat()} end={chunk_end.isoformat()} candles={len(candles)}", flush=True)
                last_error = None
                break
            except Exception as error:  # network retries are bounded and reported
                last_error = error
                time.sleep(2 ** attempt)
        if last_error is not None:
            raise RuntimeError(f"Coinbase import failed at {cursor.isoformat()}") from last_error
        cursor = chunk_end
        time.sleep(.12)
    print(f"DONE bot_id={args.bot_id} imported={imported} source=coinbase:BTC-USD", flush=True)


if __name__ == "__main__":
    main()
