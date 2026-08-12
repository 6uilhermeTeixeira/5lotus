from __future__ import annotations

import argparse
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path


PACKAGE = "dukascopy-node@1.50.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download resumable Dukascopy XAUUSD tick files.")
    parser.add_argument("--from-date", type=date.fromisoformat, default=date(2025, 10, 15))
    parser.add_argument("--to-date", type=date.fromisoformat, default=date(2026, 4, 15))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--pause-seconds", type=float, default=60.0)
    parser.add_argument("--max-retries", type=int, default=8)
    return parser.parse_args()


def expected_file(output: Path, current: date, following: date) -> Path:
    return output / f"xauusd-tick-{current.isoformat()}-{following.isoformat()}.csv"


def valid_csv(path: Path) -> bool:
    return path.is_file() and path.with_suffix(path.suffix + ".complete").is_file()


def download_day(args: argparse.Namespace, current: date, following: date) -> None:
    command = [
        "npx", "-y", PACKAGE,
        "-i", "xauusd",
        "-from", current.isoformat(),
        "-to", following.isoformat(),
        "-t", "tick",
        "-f", "csv",
        "-v",
        "-vu", "units",
        "-dir", str(args.output),
        "-ch",
        "-chpath", str(args.cache),
        "-bs", "2",
        "-bp", "1500",
        "-r", "3",
        "-rp", "3000",
        "-fr",
        "-s",
    ]
    target = expected_file(args.output, current, following)
    if current.weekday() >= 5:
        target.touch()
        target.with_suffix(target.suffix + ".complete").touch()
        return
    for attempt in range(args.max_retries + 1):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0 and target.is_file():
            target.with_suffix(target.suffix + ".complete").touch()
            return
        if attempt == args.max_retries:
            details = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"download failed for {current}: {details}")
        delay = min(300.0, 15.0 * (2**attempt))
        print(f"retry date={current} attempt={attempt + 1} wait={delay:.0f}s", flush=True)
        time.sleep(delay)


def main() -> None:
    args = parse_args()
    if args.from_date >= args.to_date:
        raise SystemExit("--from-date must be earlier than --to-date")
    args.output.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)

    current = args.from_date
    completed = 0
    skipped = 0
    while current < args.to_date:
        following = current + timedelta(days=1)
        target = expected_file(args.output, current, following)
        if valid_csv(target):
            skipped += 1
        else:
            download_day(args, current, following)
            completed += 1
            print(f"downloaded date={current} bytes={target.stat().st_size}", flush=True)
            time.sleep(args.pause_seconds)
        current = following

    print(f"complete downloaded={completed} reused={skipped} output={args.output}")


if __name__ == "__main__":
    main()
