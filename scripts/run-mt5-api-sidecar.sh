#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Arquivo de ambiente não encontrado: $ENV_FILE" >&2
  exit 1
fi

export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"

build_args=()
if [[ "${REBUILD:-0}" == "1" ]] || ! docker image inspect 2lotus-api-runtime:local >/dev/null 2>&1; then
  build_args+=(--build)
fi

docker compose --project-directory "$ROOT_DIR" up --detach --wait "${build_args[@]}" api

echo "API 2Lotus ativa em shadow mode na rede privada do MT5."
