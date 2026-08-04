"""Export strategies selected for retirement before destructive migrations."""

from __future__ import annotations

import gzip
import hashlib
import json
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from app.config import get_settings
from app.supabase_store import SupabaseStore


RETIRED_BOT_IDS = (
    "bot-1", "bot-2", "bot-3", "bot-4", "bot-5", "bot-8", "bot-9", "bot-10", "bot-15",
    "bot-eur-1", "bot-eur-2", "bot-eur-3", "bot-eur-4", "bot-eur-5", "bot-eur-6", "bot-eur-7",
)
TABLES = ("bots", "market_candles", "strategy_signals", "paper_trades", "trade_results", "backtest_snapshots")


def _load_rows(store: SupabaseStore, table: str, bot_id: str) -> list[object]:
    rows: list[object] = []
    offset = 0
    while True:
        query = urlencode({"id" if table == "bots" else "bot_id": f"eq.{bot_id}", "select": "*", "limit": "1000", "offset": str(offset)})
        page = store._request(f"{table}?{query}")
        if not isinstance(page, list):
            break
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
    return rows


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("../.artifacts"))
    args = parser.parse_args()
    store = SupabaseStore(get_settings())
    exported_at = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "exported_at_utc": exported_at.isoformat(),
        "retired_bot_ids": RETIRED_BOT_IDS,
        "tables": {},
    }
    table_payload = payload["tables"]
    assert isinstance(table_payload, dict)
    for table in TABLES:
        table_payload[table] = {bot_id: _load_rows(store, table, bot_id) for bot_id in RETIRED_BOT_IDS}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = exported_at.strftime("%Y%m%dT%H%M%SZ")
    archive = args.output_dir / f"retired-strategies-{stamp}.json.gz"
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    with gzip.open(archive, "wb", compresslevel=9) as handle:
        handle.write(raw)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = archive.with_suffix(".manifest.json")
    counts = {
        table: sum(len(rows) for rows in by_bot.values())
        for table, by_bot in table_payload.items()
        if isinstance(by_bot, dict)
    }
    manifest.write_text(json.dumps({"archive": archive.name, "sha256": digest, "counts": counts}, indent=2) + "\n")
    print(f"archive={archive} sha256={digest} counts={counts}", flush=True)


if __name__ == "__main__":
    main()
