#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
fi

mkdir -p "$ROOT_DIR/backups"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q '^doobyscoo-postgres'; then
    OUT_FILE="$ROOT_DIR/backups/doobyscoo_pg_${TIMESTAMP}.sql.gz"
    echo "[INFO] Dumping PostgreSQL container database to $OUT_FILE..."
    docker exec doobyscoo-postgres pg_dump -U "${POSTGRES_USER:-doobyscoo}" "${POSTGRES_DB:-doobyscoo}" | gzip > "$OUT_FILE"
    echo "[OK] Backup saved: $OUT_FILE"
    exit 0
fi

SQLITE_DB="${FALLBACK_SQLITE_PATH:-$ROOT_DIR/data/doobyscoo_server.db}"
if [[ ! -f "$SQLITE_DB" && -f "$ROOT_DIR/doobyscoo_server.db" ]]; then
    SQLITE_DB="$ROOT_DIR/doobyscoo_server.db"
fi

if [[ -f "$SQLITE_DB" ]]; then
    OUT_FILE="$ROOT_DIR/backups/doobyscoo_sqlite_${TIMESTAMP}.db"
    cp "$SQLITE_DB" "$OUT_FILE"
    echo "[OK] Database backup saved: $OUT_FILE"
else
    echo "[WARN] No active database file found to back up."
    exit 1
fi

