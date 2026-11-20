#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/data/server.pid"
MODE_FILE="$SCRIPT_DIR/data/runtime.mode"

stopped_any=0

if [[ -f "$PID_FILE" ]]; then
    PID_VAL="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$PID_VAL" ]] && kill -0 "$PID_VAL" 2>/dev/null; then
        echo "[INFO] Stopping DoobyScoo Server daemon (PID $PID_VAL)..."
        kill "$PID_VAL" 2>/dev/null || true
        for _ in {1..20}; do
            if ! kill -0 "$PID_VAL" 2>/dev/null; then
                break
            fi
            sleep 0.2
        done
        if kill -0 "$PID_VAL" 2>/dev/null; then
            kill -9 "$PID_VAL" 2>/dev/null || true
        fi
        stopped_any=1
    fi
    rm -f "$PID_FILE"
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    if [[ -f "$MODE_FILE" && "$(cat "$MODE_FILE" 2>/dev/null)" == "docker" ]] || docker ps --format '{{.Names}}' | grep -q '^doobyscoo-'; then
        echo "[INFO] Stopping Docker Compose containers..."
        if docker compose version >/dev/null 2>&1; then
            docker compose --profile https down >/dev/null 2>&1 || true
        elif command -v docker-compose >/dev/null 2>&1; then
            docker-compose down >/dev/null 2>&1 || true
        fi
        stopped_any=1
    fi
fi

rm -f "$MODE_FILE"

if [[ "$stopped_any" -eq 1 ]]; then
    echo "[OK] DoobyScoo Multiplayer Server stopped cleanly."
else
    echo "[INFO] DoobyScoo Multiplayer Server was not running."
fi

