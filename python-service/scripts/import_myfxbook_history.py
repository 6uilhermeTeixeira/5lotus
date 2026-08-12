from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path


HEADER = (
    "Open Date,Close Date,Symbol,Action,Lots,SL,TP,Open Price,Close Price,Pips,Profit,"
    "Duration (DD:HH:MM:SS),Change %"
)
TRADE_PATTERN = re.compile(
    r"(?P<open_date>\d{2}/\d{2}/\d{4} \d{2}:\d{2}),"
    r"(?P<close_date>\d{2}/\d{2}/\d{4} \d{2}:\d{2}),"
    r"(?P<symbol>[A-Z0-9._-]+),(?P<action>Buy|Sell),"
    r"(?P<lots>-?\d+(?:\.\d+)?),(?P<sl>-?\d+(?:\.\d+)?),(?P<tp>-?\d+(?:\.\d+)?),"
    r"(?P<open_price>-?\d+(?:\.\d+)?),(?P<close_price>-?\d+(?:\.\d+)?),"
    r"(?P<pips>-?\d+(?:\.\d+)?),(?P<profit>-?\d+(?:\.\d+)?),"
    r"(?P<duration>\d{2}:\d{2}:\d{2}:\d{2}),(?P<change_percent>-?\d+(?:\.\d+)?)"
)
EXPECTED = {
    "trade_count": 773,
    "buy_count": 398,
    "sell_count": 375,
    "lots_total": Decimal("77.30"),
    "profit_total_usd": Decimal("15251.80"),
    "non_losing_trades": 654,
}
SOURCE_TIMEZONE = "Europe/Helsinki"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize pasted Myfxbook strategy history.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def duration_seconds(value: str) -> int:
    days, hours, minutes, seconds = (int(part) for part in value.split(":"))
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def iso_datetime(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y %H:%M").isoformat(timespec="minutes")


def main() -> None:
    args = parse_args()
    raw = args.input.read_text(encoding="utf-8")
    header_at = raw.find(HEADER)
    if header_at < 0:
        raise SystemExit("Myfxbook header not found")
    source = raw[header_at + len(HEADER) :]
    matches = list(TRADE_PATTERN.finditer(source))
    if not matches:
        raise SystemExit("No Myfxbook trades found")

    rows: list[dict[str, str | int]] = []
    for index, match in enumerate(matches, start=1):
        item = match.groupdict()
        rows.append(
            {
                "source_row": index,
                "open_time_local": iso_datetime(item["open_date"]),
                "close_time_local": iso_datetime(item["close_date"]),
                "source_timezone": SOURCE_TIMEZONE,
                "symbol": item["symbol"],
                "action": item["action"].lower(),
                "lots": item["lots"],
                "stop_loss": item["sl"],
                "take_profit": item["tp"],
                "open_price": item["open_price"],
                "close_price": item["close_price"],
                "pips": item["pips"],
                "profit_usd": item["profit"],
                "duration_seconds": duration_seconds(item["duration"]),
                "change_percent": item["change_percent"],
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    action_counts = Counter(str(row["action"]) for row in rows)
    symbol_counts = Counter(str(row["symbol"]) for row in rows)
    lots = sum(Decimal(str(row["lots"])) for row in rows)
    profits = [Decimal(str(row["profit_usd"])) for row in rows]
    observed = {
        "trade_count": len(rows),
        "buy_count": action_counts["buy"],
        "sell_count": action_counts["sell"],
        "lots_total": lots,
        "profit_total_usd": sum(profits),
        "non_losing_trades": sum(profit >= 0 for profit in profits),
    }
    if observed != EXPECTED:
        raise SystemExit(f"Myfxbook totals mismatch: expected={EXPECTED!r} observed={observed!r}")
    report = {
        "source": "Myfxbook HappyForex 3.1.1 strategy 372813, pasted history",
        "source_url": "https://www.myfxbook.com/strategies/happyforex-311/372813",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "timezone": SOURCE_TIMEZONE,
        "trade_count": len(rows),
        "actions": dict(sorted(action_counts.items())),
        "symbols": dict(sorted(symbol_counts.items())),
        "lots_total": str(lots),
        "winning_trades": sum(profit > 0 for profit in profits),
        "non_losing_trades": observed["non_losing_trades"],
        "losing_trades": sum(profit < 0 for profit in profits),
        "flat_trades": sum(profit == 0 for profit in profits),
        "profit_total_usd": str(sum(profits)),
        "first_open_time_local": min(str(row["open_time_local"]) for row in rows),
        "last_open_time_local": max(str(row["open_time_local"]) for row in rows),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "published_totals_match": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
