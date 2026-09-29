#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

SERVICE_HOST="${DAYTRADE_HOST:-127.0.0.1}"
SERVICE_PORT="${DAYTRADE_PORT:-7775}"

cd "$ROOT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime not found at $PYTHON_BIN" >&2
  echo "Create the virtualenv first with: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

"$PYTHON_BIN" -m uvicorn app.main:app --host "$SERVICE_HOST" --port "$SERVICE_PORT" --app-dir "$ROOT_DIR"
