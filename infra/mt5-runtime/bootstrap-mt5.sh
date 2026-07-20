#!/usr/bin/env bash
set -euo pipefail

WINE_CMD="${WINE_CMD:-wine}"
MT5_URL="${MT5_URL:-https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe}"
WEBVIEW_URL="${WEBVIEW_URL:-https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/f2910a1e-e5a6-4f17-b52d-7faf525d17f8/MicrosoftEdgeWebview2Setup.exe}"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-/data/downloads}"
PREFIX_DIR="${WINEPREFIX:-/data/mt5-prefix}"
LOG_DIR="${LOG_DIR:-/data/logs}"
HOME_DIR="${HOME_DIR:-/data/home}"
DISPLAY_ID="${DISPLAY_ID:-:99}"
START_X_STACK="${START_X_STACK:-1}"

mkdir -p "$DOWNLOAD_DIR" "$PREFIX_DIR" "$LOG_DIR" "$HOME_DIR"

export WINEPREFIX="$PREFIX_DIR"
export WINEARCH="${WINEARCH:-win64}"
export DISPLAY="$DISPLAY_ID"
export HOME="$HOME_DIR"

if ! command -v "$WINE_CMD" >/dev/null 2>&1; then
  echo "wine runtime not found at $WINE_CMD" >&2
  exit 1
fi

if [[ ! -f "$DOWNLOAD_DIR/mt5setup.exe" ]]; then
  curl -L "$MT5_URL" --output "$DOWNLOAD_DIR/mt5setup.exe"
fi

if [[ ! -f "$DOWNLOAD_DIR/webview2.exe" ]]; then
  curl -L "$WEBVIEW_URL" --output "$DOWNLOAD_DIR/webview2.exe"
fi

PIDS=()

cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

if [[ "$START_X_STACK" == "1" ]]; then
  Xvfb "$DISPLAY" -screen 0 1280x720x24 >"$LOG_DIR/xvfb-mt5.log" 2>&1 &
  PIDS+=("$!")
  sleep 2

  if command -v openbox >/dev/null 2>&1; then
    openbox >"$LOG_DIR/openbox-mt5.log" 2>&1 &
    PIDS+=("$!")
  fi
fi

echo "Initializing wine prefix at $WINEPREFIX"
"$WINE_CMD" wineboot -i >"$LOG_DIR/wineboot-mt5.log" 2>&1 || true

echo "Installing WebView2 runtime"
"$WINE_CMD" "$DOWNLOAD_DIR/webview2.exe" /silent /install >"$LOG_DIR/webview2-mt5.log" 2>&1 || true

echo "Launching MetaTrader 5 installer"
echo "If the installer requires interaction, attach to the container display flow in the next setup step."
"$WINE_CMD" "$DOWNLOAD_DIR/mt5setup.exe" >"$LOG_DIR/mt5setup.log" 2>&1 || true

echo "bootstrap_finished=yes"
echo "wine_prefix=$WINEPREFIX"
echo "downloads_dir=$DOWNLOAD_DIR"
echo "logs=$LOG_DIR"
