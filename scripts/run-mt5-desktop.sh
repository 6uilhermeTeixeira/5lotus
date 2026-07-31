#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"

mkdir -p \
  "$RUNTIME_DIR/downloads" \
  "$RUNTIME_DIR/mt5-prefix" \
  "$RUNTIME_DIR/logs" \
  "$RUNTIME_DIR/home"

export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

build_args=()
if [[ "${REBUILD:-0}" == "1" ]] || ! docker image inspect 2lotus-mt5-runtime:local >/dev/null 2>&1; then
  build_args+=(--build)
fi

docker compose --project-directory "$ROOT_DIR" up --detach --wait "${build_args[@]}" mt5

echo "Desktop MT5 persistente ativo em http://127.0.0.1:6080/vnc.html?host=127.0.0.1&port=6080"
