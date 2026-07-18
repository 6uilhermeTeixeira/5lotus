#!/usr/bin/env bash
set -euo pipefail

WINE_CMD="/usr/lib/wine/wine"

if [[ ! -x "$WINE_CMD" ]]; then
  echo "wine runtime not found at $WINE_CMD" >&2
  exit 1
fi

echo "wine_cmd=$WINE_CMD"
"$WINE_CMD" --version

if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "xvfb-run not found" >&2
  exit 1
fi

echo "xvfb_ok=yes"
echo "runtime_ok=yes"
