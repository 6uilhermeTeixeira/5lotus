#!/usr/bin/env bash
set -euo pipefail

DISPLAY_ID="${DISPLAY_ID:-:99}"
DISPLAY_NUM="${DISPLAY_ID#:}"
SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1440x900x24}"
RFB_PORT="${RFB_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
LOG_DIR="${LOG_DIR:-/data/logs}"
HOME_DIR="${HOME_DIR:-/data/home}"
PREFIX_DIR="${WINEPREFIX:-/data/mt5-prefix}"

mkdir -p "$LOG_DIR" "$HOME_DIR" "$PREFIX_DIR"

export DISPLAY="$DISPLAY_ID"
export HOME="$HOME_DIR"
export WINEPREFIX="$PREFIX_DIR"
export WINEARCH="${WINEARCH:-win64}"

PIDS=()

cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

# Container restarts preserve /tmp. Remove only the stale artifacts for this
# dedicated display before starting a fresh X server.
rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}"

Xvfb "$DISPLAY" -screen 0 "$SCREEN_GEOMETRY" >"$LOG_DIR/xvfb-remote.log" 2>&1 &
PIDS+=("$!")
sleep 2

if command -v openbox >/dev/null 2>&1; then
  openbox >"$LOG_DIR/openbox-remote.log" 2>&1 &
  PIDS+=("$!")
fi

x11vnc \
  -display "$DISPLAY" \
  -rfbport "$RFB_PORT" \
  -forever \
  -shared \
  -noxrecord \
  -xkb \
  -repeat \
  -nopw \
  -quiet \
  >"$LOG_DIR/x11vnc.log" 2>&1 &
PIDS+=("$!")

websockify --web /usr/share/novnc/ "$NOVNC_PORT" "127.0.0.1:$RFB_PORT" >"$LOG_DIR/novnc.log" 2>&1 &
PIDS+=("$!")

START_X_STACK=0 bootstrap-mt5 >"$LOG_DIR/bootstrap-session.log" 2>&1 &
PIDS+=("$!")

echo "remote_desktop=yes"
echo "display=$DISPLAY"
echo "vnc_port=$RFB_PORT"
echo "novnc_port=$NOVNC_PORT"
echo "novnc_url=http://127.0.0.1:${NOVNC_PORT}/vnc.html?host=127.0.0.1&port=${NOVNC_PORT}"
echo "bootstrap_log=$LOG_DIR/bootstrap-session.log"
echo "Attach in the browser and complete the MT5 and WebView2 installers if they require interaction."

# The container must exit when any critical runtime process exits so Docker's
# restart policy can recover the complete demo harness.
wait -n "${PIDS[0]}" "${PIDS[2]}" "${PIDS[3]}"
echo "A critical MT5 runtime process exited; requesting container restart." >&2
exit 1
