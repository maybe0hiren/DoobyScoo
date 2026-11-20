#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/logs/server.log"
FOLLOW=0
LINES=50

for arg in "$@"; do
    case "$arg" in
        -f|--follow)
            FOLLOW=1
            ;;
        -n=*)
            LINES="${arg#*=}"
            ;;
    esac
done

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' | grep -q '^doobyscoo-backend'; then
        if [[ "$FOLLOW" -eq 1 ]]; then
            docker logs -f --tail "$LINES" doobyscoo-backend
        else
            docker logs --tail "$LINES" doobyscoo-backend
        fi
        exit 0
    fi
fi

if [[ ! -f "$LOG_FILE" ]]; then
    echo "[INFO] No log file found yet at $LOG_FILE"
    exit 0
fi

if [[ "$FOLLOW" -eq 1 ]]; then
    tail -n "$LINES" -f "$LOG_FILE"
else
    tail -n "$LINES" "$LOG_FILE"
fi

