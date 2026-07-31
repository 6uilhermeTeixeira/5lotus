#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
HARNESS_ID="2lotus-demo-shadow"
RUN_ID="health-$(date -u +%Y%m%dT%H%M%SZ)"
STARTED_AT_MS="$(date +%s%3N)"

emit() {
  local step="$1"
  local status="$2"
  local message="$3"
  local error_code="${4:-}"
  local now_ms duration
  now_ms="$(date +%s%3N)"
  duration="$((now_ms - STARTED_AT_MS))"
  STEP="$step" STATUS="$status" MESSAGE="$message" ERROR_CODE="$error_code" \
    HARNESS_ID="$HARNESS_ID" RUN_ID="$RUN_ID" DURATION_MS="$duration" \
    python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

event = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "level": "info" if os.environ["STATUS"] == "passed" else "error",
    "message": os.environ["MESSAGE"],
    "harness_id": os.environ["HARNESS_ID"],
    "run_id": os.environ["RUN_ID"],
    "step": os.environ["STEP"],
    "status": os.environ["STATUS"],
    "duration_ms": int(os.environ["DURATION_MS"]),
    "executor": "docker_compose",
}
if os.environ["ERROR_CODE"]:
    event["error_code"] = os.environ["ERROR_CODE"]
print(json.dumps(event, ensure_ascii=False))
PY
}

fail() {
  emit "$1" "failed" "$2" "$3"
  exit 1
}

[[ -f "$ENV_FILE" ]] || fail "load_config" "Arquivo .env ausente" "config_missing"

mt5_state="$(docker inspect 2lotus-mt5-desktop --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}no-health{{end}}' 2>/dev/null || true)"
api_state="$(docker inspect 2lotus-api --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}no-health{{end}}' 2>/dev/null || true)"

[[ "$mt5_state" == "running/healthy" ]] || fail "check_mt5" "MT5 não está saudável: ${mt5_state:-missing}" "mt5_unhealthy"
emit "check_mt5" "passed" "MT5 está ativo e saudável"

[[ "$api_state" == "running/healthy" ]] || fail "check_api" "API não está saudável: ${api_state:-missing}" "api_unhealthy"

config_json="$(docker exec 2lotus-mt5-desktop curl --fail --silent http://127.0.0.1:8000/config)" \
  || fail "check_api" "Endpoint /config da API não respondeu" "api_unreachable"

CONFIG_JSON="$config_json" python3 - <<'PY' || fail "check_safety" "API não está travada em shadow mode" "unsafe_config"
import json
import os

config = json.loads(os.environ["CONFIG_JSON"])
assert config["fimath_mode"] == "shadow"
assert config["enable_live_decisions"] is False
assert config["fimath_flow_policy"] == "veto"
assert config["fimath_flow_window_seconds"] == 300
assert config["fimath_min_closed_paper_trades"] >= 30
assert config["results_store"] == "SUPABASE"
assert config["supabase_results_configured"] is True
PY
emit "check_safety" "passed" "API confirmada em shadow mode, sem decisões executáveis"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

current_m5_start="$(date -u -d "@$(( $(date +%s) / 300 * 300 ))" '+%Y-%m-%dT%H:%M:%SZ')"
latest_candle="$(
  curl --fail --silent \
    "$DAYTRADE_SUPABASE_URL/rest/v1/market_candles?select=timestamp_utc,created_at,updated_at&bot_id=eq.bot-1&timestamp_utc=lt.$current_m5_start&order=timestamp_utc.desc&limit=1" \
    -H "apikey: $DAYTRADE_SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $DAYTRADE_SUPABASE_SERVICE_ROLE_KEY"
)" || fail "check_persistence" "Não foi possível consultar o último candle" "supabase_unreachable"

freshness="$(
  LATEST_CANDLE="$latest_candle" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

rows = json.loads(os.environ["LATEST_CANDLE"])
assert isinstance(rows, list)
if not rows:
    print("missing\t-1")
else:
    activity_at = max(rows[0]["created_at"], rows[0]["updated_at"])
    activity = datetime.fromisoformat(activity_at)
    age_seconds = max(0, int((datetime.now(timezone.utc) - activity).total_seconds()))
    print(f"{activity_at}\t{age_seconds}")
PY
)" || fail "check_persistence" "Resposta inválida ao consultar candles" "invalid_persistence_response"

IFS=$'\t' read -r candle_created candle_age_seconds <<<"$freshness"
max_candle_age_seconds="${MAX_CANDLE_AGE_SECONDS:-900}"

if [[ "$candle_age_seconds" -lt 0 ]]; then
  fail "check_market_data" "Nenhum candle persistido para bot-1" "market_data_missing"
fi

if [[ "$candle_age_seconds" -gt "$max_candle_age_seconds" ]]; then
  fail "check_market_data" "Último candle está desatualizado: created_at=$candle_created age_seconds=$candle_age_seconds" "market_data_stale"
fi

emit "check_market_data" "passed" "Candles atualizados: created_at=$candle_created age_seconds=$candle_age_seconds"
emit "runtime_health" "passed" "Harness demo/shadow do 2Lotus está operacional"
