#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FORCE_NATIVE=0
PORT_OVERRIDE=""

for arg in "$@"; do
    case "$arg" in
        --native)
            FORCE_NATIVE=1
            ;;
        --port=*)
            PORT_OVERRIDE="${arg#*=}"
            ;;
    esac
done

mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/logs" "$SCRIPT_DIR/backups"

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
fi

if [[ -n "$PORT_OVERRIDE" ]]; then
    sed -i "s/^PORT=.*/PORT=${PORT_OVERRIDE}/" "$SCRIPT_DIR/.env"
fi

set -a
# shellcheck disable=SC1091
source "$SCRIPT_DIR/.env"
set +a

APP_PORT="${PORT:-8000}"
APP_HOST="${HOST:-0.0.0.0}"
PID_FILE="$SCRIPT_DIR/data/server.pid"
MODE_FILE="$SCRIPT_DIR/data/runtime.mode"
LOG_FILE="$SCRIPT_DIR/logs/server.log"

docker_available() {
    if [[ "$FORCE_NATIVE" -eq 1 ]]; then
        return 1
    fi
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

run_docker_compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

wait_for_health() {
    local target_url="http://127.0.0.1:${APP_PORT}/health"
    for _ in {1..30}; do
        if curl -fsS "$target_url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

if docker_available; then
    echo "[INFO] Starting DoobyScoo Server stack via Docker Compose (PostgreSQL + Backend)..."
    if [[ -n "${SERVER_DOMAIN:-}" ]]; then
        echo "[INFO] Domain '${SERVER_DOMAIN}' configured — enabling Caddy HTTPS reverse proxy..."
        if run_docker_compose --profile https up --build -d >>"$LOG_FILE" 2>&1; then
            echo "docker" > "$MODE_FILE"
            if wait_for_health; then
                echo "[OK] DoobyScoo Server (Docker + HTTPS) is online on port ${APP_PORT} (and 80/443)."
                exit 0
            fi
        fi
    else
        if run_docker_compose up --build -d >>"$LOG_FILE" 2>&1; then
            echo "docker" > "$MODE_FILE"
            if wait_for_health; then
                echo "[OK] DoobyScoo Server (Docker + PostgreSQL) is online at http://127.0.0.1:${APP_PORT}"
                exit 0
            fi
        fi
    fi
    echo "[WARN] Docker startup did not complete cleanly; falling back to local Python daemon mode..."
fi

# Native Python Daemon Mode
if [[ -f "$PID_FILE" ]]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[INFO] DoobyScoo Server is already running (PID $OLD_PID) on port ${APP_PORT}."
        exit 0
    fi
    rm -f "$PID_FILE"
fi

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    if [[ -x "$SCRIPT_DIR/../doobyscoo-agent/.venv/bin/python" ]]; then
        PYTHON_BIN="$SCRIPT_DIR/../doobyscoo-agent/.venv/bin/python"
    else
        PYTHON_BIN="$(command -v python3)"
    fi
fi

echo "[INFO] Starting DoobyScoo Multiplayer Server daemon on ${APP_HOST}:${APP_PORT}..."
PYTHONPATH="$SCRIPT_DIR" nohup "$PYTHON_BIN" -m app.main --host "$APP_HOST" --port "$APP_PORT" >>"$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "native" > "$MODE_FILE"

if wait_for_health; then
    echo "[OK] DoobyScoo Multiplayer Server started (PID $NEW_PID) at http://${APP_HOST}:${APP_PORT}"
else
    echo "[ERROR] Server failed health check on port ${APP_PORT}. Recent logs:"
    tail -n 25 "$LOG_FILE" || true
    exit 1
fi

