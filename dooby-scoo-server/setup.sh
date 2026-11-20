#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NON_INTERACTIVE=0
FORCE_NATIVE=0
PORT_OVERRIDE=""

for arg in "$@"; do
    case "$arg" in
        --non-interactive|-y)
            NON_INTERACTIVE=1
            ;;
        --native)
            FORCE_NATIVE=1
            ;;
        --port=*)
            PORT_OVERRIDE="${arg#*=}"
            ;;
    esac
done

echo "============================================================"
echo "  DoobyScoo Authoritative Multiplayer Server — Setup"
echo "============================================================"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "[ERROR] Unsupported OS: $(uname -s). A Linux server OS is required."
    exit 1
fi

if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    echo "[INFO] Detected Linux Distribution: ${PRETTY_NAME:-Linux}"
fi

mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/logs" "$SCRIPT_DIR/backups" "$SCRIPT_DIR/scripts"

generate_secret() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "${1:-32}"
    else
        python3 -c "import secrets; print(secrets.token_hex(${1:-32}))"
    fi
}

ENV_FILE="$SCRIPT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    echo "[INFO] Existing .env found — preserving existing configuration and secrets."
else
    echo "[INFO] Creating new production .env with generated cryptographic secrets..."
    SERVER_DOMAIN_INPUT=""
    ADMIN_EMAIL_INPUT=""
    if [[ "$NON_INTERACTIVE" -eq 0 && -t 0 ]]; then
        read -r -p "Enter server domain (optional, press Enter to skip): " SERVER_DOMAIN_INPUT || true
        if [[ -n "$SERVER_DOMAIN_INPUT" ]]; then
            read -r -p "Enter administrator email for HTTPS certificates (optional): " ADMIN_EMAIL_INPUT || true
        fi
    fi

    JWT_SEC="$(generate_secret 32)"
    PG_PASS="$(generate_secret 16)"
    CFG_PORT="${PORT_OVERRIDE:-8000}"

    cat > "$ENV_FILE" <<EOF
APP_NAME="DoobyScoo Multiplayer Server"
APP_ENV=production
HOST=0.0.0.0
PORT=${CFG_PORT}
POSTGRES_USER=doobyscoo
POSTGRES_PASSWORD=${PG_PASS}
POSTGRES_DB=doobyscoo
DATABASE_URL=postgresql://doobyscoo:${PG_PASS}@localhost:5432/doobyscoo
FALLBACK_SQLITE_PATH=${SCRIPT_DIR}/data/doobyscoo_server.db
JWT_SECRET_KEY=${JWT_SEC}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
CORS_ORIGINS=*
SERVER_DOMAIN=${SERVER_DOMAIN_INPUT}
ADMIN_EMAIL=${ADMIN_EMAIL_INPUT}
MATCH_EXPIRATION_SECONDS=600
MATCHMAKING_EXPIRATION_SECONDS=180
MATCHMAKING_INITIAL_TROPHY_RANGE=200
MATCHMAKING_RANGE_EXPANSION_PER_SEC=25
MAX_MATCH_STEPS=300
TROPHY_WIN_REWARD=25
TROPHY_LOSS_PENALTY=15
TROPHY_DRAW_REWARD=5
XP_MATCH_PARTICIPATION=25
XP_MATCH_WIN=50
XP_PERSONAL_BEST=30
XP_LEAGUE_ADVANCEMENT=100
RATE_LIMIT_PER_MINUTE=240
AUTH_RATE_LIMIT_PER_MINUTE=60
MAX_REQUEST_BYTES=1048576
EOF
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    echo "[INFO] Generated .env configuration."
fi

if [[ -n "$PORT_OVERRIDE" ]]; then
    sed -i "s/^PORT=.*/PORT=${PORT_OVERRIDE}/" "$ENV_FILE"
fi

# Load environment variables safely
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

ensure_python_venv() {
    VENV_DIR="$SCRIPT_DIR/.venv"
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        echo "[INFO] Creating Python virtual environment in $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
    fi
    if ! "$VENV_DIR/bin/python" -c "import tornado, argon2" >/dev/null 2>&1; then
        echo "[INFO] Installing Python backend dependencies into $VENV_DIR..."
        "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
        "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
    else
        echo "[INFO] Python dependencies already verified in $VENV_DIR."
    fi
}

try_install_system_dependencies() {
    if [[ "$EUID" -ne 0 ]]; then
        return 0
    fi
    if ! command -v docker >/dev/null 2>&1 && [[ "$FORCE_NATIVE" -eq 0 ]]; then
        echo "[INFO] Checking package manager to install Docker / PostgreSQL if needed..."
        if command -v apt-get >/dev/null 2>&1; then
            apt-get update -y >/dev/null 2>&1 || true
            apt-get install -y docker.io docker-compose-plugin python3-venv python3-pip postgresql postgresql-contrib curl >/dev/null 2>&1 || true
            systemctl enable --now docker >/dev/null 2>&1 || true
            systemctl enable --now postgresql >/dev/null 2>&1 || true
        elif command -v dnf >/dev/null 2>&1; then
            dnf install -y docker docker-compose-plugin python3-pip postgresql-server curl >/dev/null 2>&1 || true
            systemctl enable --now docker >/dev/null 2>&1 || true
        elif command -v pacman >/dev/null 2>&1; then
            pacman -Sy --noconfirm docker docker-compose python-pip postgresql curl >/dev/null 2>&1 || true
            systemctl enable --now docker >/dev/null 2>&1 || true
        fi
    fi
}

configure_native_postgres_if_available() {
    if command -v psql >/dev/null 2>&1 && [[ "$EUID" -eq 0 ]]; then
        if systemctl is-active --quiet postgresql 2>/dev/null; then
            echo "[INFO] Configuring local PostgreSQL database and user..."
            su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER:-doobyscoo}'\" | grep -q 1 || psql -c \"CREATE USER ${POSTGRES_USER:-doobyscoo} WITH PASSWORD '${POSTGRES_PASSWORD}';\"" >/dev/null 2>&1 || true
            su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB:-doobyscoo}'\" | grep -q 1 || psql -c \"CREATE DATABASE ${POSTGRES_DB:-doobyscoo} OWNER ${POSTGRES_USER:-doobyscoo};\"" >/dev/null 2>&1 || true
        fi
    fi
}

install_systemd_service() {
    if [[ "$EUID" -ne 0 ]] || ! command -v systemctl >/dev/null 2>&1; then
        return 0
    fi
    SERVICE_FILE="/etc/systemd/system/doobyscoo-server.service"
    echo "[INFO] Configuring systemd service ($SERVICE_FILE) for automatic startup on reboot..."
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=DoobyScoo Authoritative Multiplayer Backend
After=network.target docker.service postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/env bash ${SCRIPT_DIR}/start.sh
ExecStop=/usr/bin/env bash ${SCRIPT_DIR}/stop.sh
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable doobyscoo-server.service >/dev/null 2>&1 || true
}

try_install_system_dependencies
ensure_python_venv
configure_native_postgres_if_available

echo "[INFO] Initializing database schema and applying migrations..."
PYTHONPATH="$SCRIPT_DIR" "$SCRIPT_DIR/.venv/bin/python" -c "
from app.config import settings
from app.database.session import initDatabase
engine = initDatabase()
backend = 'PostgreSQL' if engine.isPostgres else f'Relational SQLite ({engine.sqlitePath})'
print(f'[INFO] Database schema initialized and verified on {backend}.')
"

install_systemd_service

echo "[INFO] Starting DoobyScoo Multiplayer Server..."
if [[ "$FORCE_NATIVE" -eq 1 ]]; then
    bash "$SCRIPT_DIR/start.sh" --native
else
    bash "$SCRIPT_DIR/start.sh"
fi

echo ""
bash "$SCRIPT_DIR/status.sh"
