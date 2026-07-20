#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-2lotus-mt5-runtime}"
RUNTIME_DIR="${RUNTIME_DIR:-$ROOT_DIR/.runtime}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PORT="${VNC_PORT:-5900}"
CONTAINER_NAME="${CONTAINER_NAME:-2lotus-mt5-desktop}"

mkdir -p \
  "$RUNTIME_DIR/downloads" \
  "$RUNTIME_DIR/mt5-prefix" \
  "$RUNTIME_DIR/logs" \
  "$RUNTIME_DIR/home"

echo "Abrindo desktop remoto local do MT5 em http://127.0.0.1:${NOVNC_PORT}/vnc.html?host=127.0.0.1&port=${NOVNC_PORT}"
echo "Container: ${CONTAINER_NAME}"

docker run --rm -it \
  --name "$CONTAINER_NAME" \
  --user "$(id -u):$(id -g)" \
  -p "127.0.0.1:${NOVNC_PORT}:${NOVNC_PORT}" \
  -p "127.0.0.1:${VNC_PORT}:${VNC_PORT}" \
  -e HOME=/data/home \
  -e HOME_DIR=/data/home \
  -e DOWNLOAD_DIR=/data/downloads \
  -e WINEPREFIX=/data/mt5-prefix \
  -e LOG_DIR=/data/logs \
  -e RFB_PORT="$VNC_PORT" \
  -e NOVNC_PORT="$NOVNC_PORT" \
  -v "$RUNTIME_DIR/downloads:/data/downloads" \
  -v "$RUNTIME_DIR/mt5-prefix:/data/mt5-prefix" \
  -v "$RUNTIME_DIR/logs:/data/logs" \
  -v "$RUNTIME_DIR/home:/data/home" \
  "$IMAGE_NAME" \
  start-remote-desktop
