#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
failures=0

pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

command -v docker >/dev/null 2>&1 && pass "Docker is installed" || fail "Docker is not installed"
docker compose version >/dev/null 2>&1 && pass "Docker Compose is available" || fail "Docker Compose is unavailable"
docker compose --project-directory "$ROOT_DIR" config --quiet >/dev/null 2>&1 \
  && pass "compose.yaml is valid" || fail "compose.yaml is invalid"

if [[ -f "$ENV_FILE" ]]; then
  pass ".env exists"
  for key in DAYTRADE_SUPABASE_URL DAYTRADE_SUPABASE_SERVICE_ROLE_KEY DAYTRADE_DASHBOARD_PASSWORD DAYTRADE_SESSION_SECRET DAYTRADE_INGEST_API_KEY; do
    value="$(sed -n "s/^${key}=//p" "$ENV_FILE" | tail -1)"
    if [[ -z "$value" || "$value" == PREENCHA_* ]]; then fail "$key is missing or still a placeholder"; else pass "$key is configured"; fi
  done
else
  fail ".env is missing; copy .env.example and fill secrets locally"
fi

expected='["core-combined-v3","core-multitimeframe-v3","core-stochastic-v3","core-zigzag-v3"]'
actual="$(jq -c '[.[] | select(.active == true) | .id] | sort' "$ROOT_DIR/python-service/data/bots.json")"
[[ "$actual" == "$expected" ]] && pass "only the four V3 catalog entries are active" || fail "active catalog differs from the four V3 entries: $actual"

for bot in core-zigzag-v3 core-stochastic-v3 core-multitimeframe-v3 core-combined-v3; do
  [[ -s "$ROOT_DIR/python-service/data/backtests/$bot-365.json" ]] \
    && pass "$bot annual backtest exists" || fail "$bot annual backtest is missing"
done

if docker image inspect 2lotus-mt5-runtime:local >/dev/null 2>&1; then
  pass "Wine/MT5 Docker image exists"
else
  warn "Wine/MT5 image is not built; run ./scripts/build-mt5-runtime.sh"
fi

terminal="$ROOT_DIR/.runtime/mt5-prefix/drive_c/Program Files/MetaTrader 5/terminal64.exe"
[[ -f "$terminal" ]] && pass "MT5 terminal is installed in the persistent Wine prefix" \
  || warn "MT5 terminal is not installed yet; use ./scripts/run-mt5-desktop.sh and complete setup via noVNC"

if find "$ROOT_DIR/.runtime/mt5-prefix/drive_c/users" -type f -name 'SyncLeadBridgeEA.ex5' -print -quit 2>/dev/null | grep -q .; then
  pass "compiled SyncLeadBridgeEA.ex5 was found"
else
  warn "compiled SyncLeadBridgeEA.ex5 was not found; install and compile the EA"
fi

warn "V3 profiles still have intentional shadow locks; real orders are not enabled by this preparation"
warn "Do not execute the three individual V3 bots together with the combined V3: that duplicates exposure"

if [[ "$failures" -gt 0 ]]; then
  printf '\nPreflight failed with %d blocking issue(s).\n' "$failures" >&2
  exit 1
fi
printf '\nPreparation checks passed; resolve WARN items before demo/live promotion.\n'
