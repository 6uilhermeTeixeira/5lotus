#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX_DIR="${MT5_PREFIX_DIR:-${RUNTIME_DIR:-$ROOT_DIR/.runtime}/mt5-prefix}"
SOURCE="$ROOT_DIR/mt5/experts/SyncLeadBridgeEA.mq5"

[[ -f "$SOURCE" ]] || { echo "EA source not found: $SOURCE" >&2; exit 1; }
[[ -d "$PREFIX_DIR" ]] || { echo "Wine prefix not found. Start the MT5 runtime first." >&2; exit 1; }

mapfile -t expert_dirs < <(
  {
    find "$PREFIX_DIR/drive_c/users" -type d -path '*/MetaQuotes/Terminal/*/MQL5/Experts' 2>/dev/null
    printf '%s\n' "$PREFIX_DIR/drive_c/Program Files/MetaTrader 5/MQL5/Experts"
  } | sort -u
)
if [[ "${#expert_dirs[@]}" -eq 0 ]]; then
  echo "No MT5 data directory found. Complete the terminal installation and first launch first." >&2
  exit 1
fi

for directory in "${expert_dirs[@]}"; do
  [[ -d "$directory" ]] || continue
  install -m 0644 "$SOURCE" "$directory/SyncLeadBridgeEA.mq5"
  echo "installed=$directory/SyncLeadBridgeEA.mq5"
done

echo "Open MetaEditor in noVNC and compile SyncLeadBridgeEA.mq5; verify 0 errors before attaching it."
