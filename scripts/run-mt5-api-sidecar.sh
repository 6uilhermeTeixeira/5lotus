#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
MT5_CONTAINER="${MT5_CONTAINER:-2lotus-mt5-desktop}"
API_CONTAINER="${API_CONTAINER:-2lotus-api}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo de ambiente não encontrado: $ENV_FILE" >&2
  exit 1
fi

if ! docker inspect "$MT5_CONTAINER" >/dev/null 2>&1; then
  echo "O container do MT5 não está ativo: $MT5_CONTAINER" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

docker rm -f "$API_CONTAINER" >/dev/null 2>&1 || true

docker run -d \
  --name "$API_CONTAINER" \
  --network "container:$MT5_CONTAINER" \
  -e DAYTRADE_DASHBOARD_PASSWORD \
  -e DAYTRADE_SESSION_SECRET \
  -e DAYTRADE_RESULTS_STORE \
  -e DAYTRADE_SUPABASE_URL \
  -e DAYTRADE_SUPABASE_SERVICE_ROLE_KEY \
  -e DAYTRADE_INGEST_API_KEY \
  -v "$ROOT_DIR/python-service:/app:ro" \
  -w /app \
  python:3.12-slim \
  sh -c 'pip install --no-cache-dir -r requirements.txt >/tmp/pip.log && exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000'

echo "API 2Lotus iniciada como $API_CONTAINER na rede privada do MT5."
