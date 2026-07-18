#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-daytrade-mt5-runtime}"
RUNTIME_DIR="${RUNTIME_DIR:-$ROOT_DIR/.runtime}"

mkdir -p \
  "$RUNTIME_DIR/downloads" \
  "$RUNTIME_DIR/mt5-prefix" \
  "$RUNTIME_DIR/logs" \
  "$RUNTIME_DIR/home"

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e HOME=/data/home \
  -e HOME_DIR=/data/home \
  -e DOWNLOAD_DIR=/data/downloads \
  -e WINEPREFIX=/data/mt5-prefix \
  -e LOG_DIR=/data/logs \
  -v "$RUNTIME_DIR/downloads:/data/downloads" \
  -v "$RUNTIME_DIR/mt5-prefix:/data/mt5-prefix" \
  -v "$RUNTIME_DIR/logs:/data/logs" \
  -v "$RUNTIME_DIR/home:/data/home" \
  "$IMAGE_NAME" \
  bootstrap-mt5
