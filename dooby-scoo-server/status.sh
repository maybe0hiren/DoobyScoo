#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
    set +a
fi

APP_PORT="${PORT:-8000}"
APP_HOST="${HOST:-0.0.0.0}"
PID_FILE="$SCRIPT_DIR/data/server.pid"
MODE_FILE="$SCRIPT_DIR/data/runtime.mode"
LOG_FILE="$SCRIPT_DIR/logs/server.log"

RUNTIME_MODE="stopped"
PROC_STATUS="OFFLINE"

if [[ -f "$PID_FILE" ]]; then
    PID_VAL="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$PID_VAL" ]] && kill -0 "$PID_VAL" 2>/dev/null; then
        RUNTIME_MODE="native (PID $PID_VAL)"
        PROC_STATUS="ONLINE"
    fi
fi

if [[ "$PROC_STATUS" == "OFFLINE" ]] && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' | grep -q '^doobyscoo-backend'; then
        RUNTIME_MODE="docker-compose"
        PROC_STATUS="ONLINE"
    fi
fi

HEALTH_RESP="$(curl -fsS --max-time 3 "http://127.0.0.1:${APP_PORT}/health" 2>/dev/null || true)"
STATUS_RESP="$(curl -fsS --max-time 3 "http://127.0.0.1:${APP_PORT}/api/v1/status" 2>/dev/null || true)"

API_STATE="UNREACHABLE"
DB_BACKEND="unknown"
DB_STATE="DISCONNECTED"
WS_STATE="OFFLINE"
TOTAL_PLAYERS="0"
TOTAL_MATCHES="0"
QUEUE_COUNT="0"
WS_USERS="0"

if [[ -n "$HEALTH_RESP" ]]; then
    API_STATE="HEALTHY (/health -> 200 OK)"
    PROC_STATUS="ONLINE"
    WS_STATE="READY (ws://${APP_HOST}:${APP_PORT}/ws)"
fi

if [[ -n "$STATUS_RESP" ]]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
    if [[ ! -x "$PYTHON_BIN" ]]; then
        PYTHON_BIN="$(command -v python3)"
    fi
    eval "$("$PYTHON_BIN" -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
    print(f'DB_BACKEND=\"{d.get(\"database_backend\", \"unknown\")}\"')
    print('DB_STATE=\"CONNECTED\"')
    print(f'TOTAL_PLAYERS=\"{d.get(\"total_players\", 0)}\"')
    print(f'TOTAL_MATCHES=\"{d.get(\"total_matches\", 0)}\"')
    print(f'QUEUE_COUNT=\"{d.get(\"searching_players\", 0)}\"')
    print(f'WS_USERS=\"{d.get(\"online_ws_users\", 0)}\"')
except Exception:
    pass
" "$STATUS_RESP")"
fi

echo "============================================================"
echo "  DoobyScoo Authoritative Multiplayer Server — Status"
echo "============================================================"
echo "  Application Status : ${PROC_STATUS} (${RUNTIME_MODE})"
echo "  API Status         : ${API_STATE}"
echo "  WebSocket Status   : ${WS_STATE} (${WS_USERS} active connections)"
echo "  Database Status    : ${DB_STATE} (backend: ${DB_BACKEND})"
echo "  Listening Address  : http://${APP_HOST}:${APP_PORT}"
echo "  OpenAPI Spec       : http://127.0.0.1:${APP_PORT}/openapi.json"
if [[ -n "${SERVER_DOMAIN:-}" ]]; then
    echo "  Configured Domain  : https://${SERVER_DOMAIN} (wss://${SERVER_DOMAIN}/ws)"
fi
echo "  Registered Players : ${TOTAL_PLAYERS}"
echo "  Recorded Battles   : ${TOTAL_MATCHES} (Searching in Queue: ${QUEUE_COUNT})"
echo "------------------------------------------------------------"

if [[ -f "$LOG_FILE" ]]; then
    RECENT_ERRORS="$(grep -iE "error|exception|traceback|critical" "$LOG_FILE" | tail -n 5 || true)"
    if [[ -n "$RECENT_ERRORS" ]]; then
        echo "  Recent Errors in Log ($LOG_FILE):"
        echo "$RECENT_ERRORS" | sed 's/^/    /'
    else
        echo "  Recent Errors      : None detected in $LOG_FILE"
    fi
else
    echo "  Log File           : Not created yet ($LOG_FILE)"
fi
echo "============================================================"

if [[ "$PROC_STATUS" != "ONLINE" || "$API_STATE" == "UNREACHABLE" ]]; then
    exit 1
fi

