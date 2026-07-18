#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-daytrade-mt5-runtime}"

docker build \
  -t "$IMAGE_NAME" \
  -f "$ROOT_DIR/infra/mt5-runtime/Dockerfile" \
  "$ROOT_DIR"

echo "built_image=$IMAGE_NAME"
