#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "Arquivo de ambiente não encontrado: $ROOT_DIR/.env" >&2
  exit 1
fi

export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

mkdir -p \
  "$ROOT_DIR/.runtime/downloads" \
  "$ROOT_DIR/.runtime/mt5-prefix" \
  "$ROOT_DIR/.runtime/logs" \
  "$ROOT_DIR/.runtime/home"

build_args=()
if [[ "${REBUILD:-0}" == "1" ]] \
  || ! docker image inspect 2lotus-mt5-runtime:local >/dev/null 2>&1 \
  || ! docker image inspect 2lotus-api-runtime:local >/dev/null 2>&1; then
  build_args+=(--build)
fi

docker compose --project-directory "$ROOT_DIR" up --detach --wait "${build_args[@]}"

health_output="$(mktemp)"
trap 'rm -f "$health_output"' EXIT

for attempt in $(seq 1 24); do
  if "$ROOT_DIR/scripts/check-2lotus-runtime.sh" >"$health_output" 2>&1; then
    cat "$health_output"
    exit 0
  fi
  if [[ "$attempt" -lt 24 ]]; then
    sleep 5
  fi
done

cat "$health_output" >&2
echo "O runtime iniciou, mas não confirmou candles novos em até 2 minutos." >&2
exit 1
