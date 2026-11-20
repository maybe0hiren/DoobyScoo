# DoobyScoo Multiplayer Server (`dooby-scoo-server`)

The authoritative online competition backend for **DoobyScoo**.

It manages player accounts, Argon2id password hashing, JWT access/refresh tokens, trophy-based matchmaking, procedural competition maze generation (`10×10`, `SHA-256` signed), authoritative action-trace verification (`Score = Steps - 5 × Bones Collected`), leagues, global/league leaderboards, battle history, and live WebSocket communication.

> **Strict Architectural Separation**:
> - `dooby-scoo-server` is a clean, standalone backend application.
> - It **never** requires Godot, PyTorch, RL training dependencies, or player RL models.
> - Every player's AI Dog runs locally on their own machine via `doobyscoo-agent`, while `dooby-scoo-server` independently validates and replays submitted action traces using `AuthoritativeMazeEnvironment`.

---

## 1. One-Command Server Setup (Quickest Start)

On any supported Linux server, deploy and start the entire multiplayer backend with:

```bash
git clone <repository>
cd dooby-scoo-server
sudo bash setup.sh
```

After `setup.sh` finishes, the server is online, initialized, migrated, and configured to start automatically after a reboot.

For non-interactive deployment (or custom port configuration):

```bash
sudo bash setup.sh --non-interactive --port=8000
```

---

## 2. Managing the Server (Start, Stop, Status, Logs, Backup)

### Start the Server
```bash
sudo bash start.sh
```
*(Or without `sudo` in local user mode: `bash start.sh --native --port=8766`)*

### Stop the Server
```bash
sudo bash stop.sh
```

### Check Server Status
```bash
bash status.sh
```
Displays:
- Application & process status (`ONLINE` / `OFFLINE`)
- API health status (`/health`)
- WebSocket status (`/ws` and `/api/v1/battles/{battle_id}/ws`)
- Database connectivity & active backend (`postgresql` or `sqlite_relational`)
- Listening host, port, domain, player count, match count, and recent log errors

### View Server Logs
```bash
bash logs.sh
# Follow live logs:
bash logs.sh -f
```

### Backup the Database
```bash
bash scripts/backup_db.sh
```
Creates a timestamped database dump inside `dooby-scoo-server/backups/`.

---

## 3. Architecture & Directory Structure

```text
dooby-scoo-server/
├── app/
│   ├── main.py                      # Application entry point, /health, /api/v1/status, /openapi.json
│   ├── config.py                    # Environment & .env configuration loader
│   ├── api/
│   │   ├── auth.py                  # /api/v1/auth/* (register, login, logout, refresh, password-reset)
│   │   ├── users.py                 # /api/v1/users/me, /api/v1/users/{user_id}/stats
│   │   ├── profiles.py              # /api/v1/players/me, rank, history, events
│   │   ├── matchmaking.py           # /api/v1/matchmaking/join, cancel, status
│   │   ├── matches.py               # /api/v1/matches/{match_id}, map, submit, actions, result
│   │   ├── battles.py               # /api/v1/battles/{battle_id}, map, actions, submit, result
│   │   ├── leaderboards.py          # /api/v1/leaderboards/global, league/{league}, leagues
│   │   └── history.py               # /api/v1/history/matches, trophies
│   ├── core/
│   │   ├── framework.py             # HTTP + WebSocket server, OpenAPI generator, CORS & rate limiting
│   │   ├── security.py              # Argon2id password hashing, JWT creation & verification
│   │   ├── dependencies.py          # Bearer auth middleware & IP/auth rate limiter
│   │   ├── exceptions.py            # Structured API exceptions
│   │   └── websocket_manager.py     # Authenticated WebSocket room & event manager
│   ├── models/                      # Domain models (User, PlayerProfile, Match, MazeMap, MatchResult, TrophyHistory)
│   ├── schemas/                     # Request validators & response serializers
│   ├── services/                    # Auth, Matchmaking, Match/Battle, MapGenerator, ResultVerifier, Ranking, Progression
│   ├── database/                    # PostgreSQL & relational SQLite engine + schema migrations
│   └── rl_verification/             # AuthoritativeMazeEnvironment & deterministic action replay verifier
├── migrations/                      # Alembic migration environment & initial schema revision
├── scripts/
│   └── backup_db.sh                 # Automated PostgreSQL / SQLite backup utility
├── tests/                           # Comprehensive backend & 2-player E2E test suite
├── Caddyfile                        # Automatic HTTPS & WSS reverse proxy configuration
├── Dockerfile                       # Production container image definition
├── docker-compose.yml               # PostgreSQL + DoobyScoo Backend (+ optional Caddy HTTPS profile)
├── .env.example                     # Example environment configuration
├── setup.sh                         # One-command automated setup & deployment script
├── start.sh                         # Start backend services
├── stop.sh                          # Stop backend services
├── status.sh                        # Inspect health, DB, WS, ports, and recent errors
└── logs.sh                          # Tail or follow server logs
```

---

## 4. Requirements

- **OS**: Linux (Ubuntu, Debian, Fedora, Arch, CentOS, or any systemd/Docker-capable Linux distribution)
- **Automated Dependencies**: `setup.sh` automatically configures Python virtual environments, secrets, database schema migrations, systemd auto-start on boot, and Docker Compose (when Docker is active).

---

## 5. Configuration & `.env`

`setup.sh` automatically generates `.env` with cryptographically random secrets (`JWT_SECRET_KEY` and `POSTGRES_PASSWORD`) if `.env` does not already exist. It will never overwrite an existing `.env`.

Key variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | HTTP & WebSocket listening port |
| `DATABASE_URL` | `postgresql://doobyscoo:...@localhost:5432/doobyscoo` | PostgreSQL connection URL |
| `FALLBACK_SQLITE_PATH` | `./data/doobyscoo_server.db` | Persistent relational database path when running standalone without PostgreSQL |
| `JWT_SECRET_KEY` | *(auto-generated 64-hex secret)* | HMAC-SHA256 signing secret for access and refresh tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Refresh token lifetime |
| `SERVER_DOMAIN` | *(empty)* | Optional domain name for automatic HTTPS via Caddy |
| `ADMIN_EMAIL` | *(empty)* | Optional admin email for Let's Encrypt TLS certificates |
| `RATE_LIMIT_PER_MINUTE` | `240` | General API rate limit per IP |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `60` | Strict rate limit for `/api/v1/auth/*` endpoints |

---

## 6. Domain Configuration & HTTPS / Secure WebSockets (`WSS`)

To deploy the server on the public internet with automatic TLS (`https://` and `wss://`):

1. Point your domain's DNS `A` record to your server's public IP address and ensure ports `80` and `443` are open.
2. Set `SERVER_DOMAIN=play.yourdomain.com` and `ADMIN_EMAIL=you@yourdomain.com` in `.env` (or enter them when prompted by `sudo bash setup.sh`).
3. Run `sudo bash start.sh`.
4. Docker Compose will automatically launch the `caddy` profile using the included `Caddyfile`, obtain TLS certificates, and proxy `https://play.yourdomain.com` and `wss://play.yourdomain.com/ws` to the backend while keeping PostgreSQL private on the internal network.
5. In the Godot client's **Multiplayer Arena**, set **Multiplayer Server** to `https://play.yourdomain.com`.

---

## 7. API Documentation (`/api/v1/` & OpenAPI)

When the server is running, machine-readable OpenAPI 3.1 documentation is served at:
- `GET /openapi.json`
- `GET /api/v1/openapi.json`

### Health & Status
- `GET /health` or `GET /api/v1/health` — Liveness probe (`{"status": "ok"}`).
- `GET /api/v1/status` — Detailed runtime metrics, database backend, player/match counts, and active WebSocket count.

### Authentication
- `POST /api/v1/auth/register` — Register a new player account.
- `POST /api/v1/auth/login` — Authenticate and obtain `access_token` and `refresh_token`.
- `POST /api/v1/auth/refresh` — Rotate refresh token and issue a new access token.
- `POST /api/v1/auth/logout` — Revoke refresh token(s).
- `POST /api/v1/auth/password-reset` — Reset password.
- `GET /api/v1/auth/username-available?username=<name>` — Check username availability.

### Users & Player Profiles
- `GET /api/v1/users/me` & `GET /api/v1/players/me` — Retrieve authenticated user account and competitive profile.
- `PATCH /api/v1/users/me` & `PATCH /api/v1/players/me` — Update display name, avatar, settings, or local dog model version.
- `GET /api/v1/users/{user_id}/stats` — Retrieve player battle statistics and recent battles by user ID or username.
- `GET /api/v1/players/{username}` — Public player profile.
- `GET /api/v1/players/me/rank` — Global rank, league rank, and nearby ranked players.
- `GET /api/v1/players/me/history` — Paginated match and trophy history.
- `GET /api/v1/players/me/events` — Recover missed WebSocket events after reconnection.

### Matchmaking
- `POST /api/v1/matchmaking/join` — Enter trophy-based matchmaking queue.
- `POST /api/v1/matchmaking/cancel` — Cancel active matchmaking search.
- `GET /api/v1/matchmaking/status` — Poll current matchmaking state.

### Battles & Matches
- `GET /api/v1/battles/{battle_id}` (or `/api/v1/matches/{match_id}`) — Retrieve battle state and metadata.
- `GET /api/v1/battles/{battle_id}/map` (or `/api/v1/matches/{match_id}/map`) — Download assigned 10×10 competition maze JSON and SHA-256 hash.
- `POST /api/v1/battles/{battle_id}/actions` (or `/api/v1/matches/{match_id}/submit`) — Submit the local Dog's action trace for authoritative server replay and verification.
- `GET /api/v1/battles/{battle_id}/result` (or `/api/v1/matches/{match_id}/result`) — Retrieve verified result, winner, and trophy deltas.
- `GET /api/v1/battles/history` (or `/api/v1/matches/history`) — Paginated battle history.

### Leaderboards
- `GET /api/v1/leaderboard` (or `/api/v1/leaderboards/global`) — Paginated global leaderboard (`limit`, `offset`, optional `league`).
- `GET /api/v1/leaderboards/league/{league}` — League-specific leaderboard (`Beginner` through `Master`).
- `GET /api/v1/leaderboards/leagues` — List all leagues and trophy thresholds.

### WebSockets
- `WS /ws?token=<access_token>&last_event_id=<id>&since_seq=<seq>` — Global authenticated live event stream.
- `WS /api/v1/battles/{battle_id}/ws?token=<access_token>` — Battle-room-specific authenticated WebSocket (verifies that the connecting user is a participant in `battle_id` and rejects outsiders with code `4003 Forbidden`).

---

## 8. Updating the Server

```bash
cd dooby-scoo-server
git pull
sudo bash setup.sh
```
`setup.sh` is idempotent: it preserves your `.env` and database volumes while applying any new migrations and restarting the service.

---

## 9. Troubleshooting

- **Port already in use**: Change `PORT=8766` in `.env` (or pass `--port=8766` to `setup.sh` / `start.sh`) and restart with `bash stop.sh && bash start.sh`.
- **Inspecting errors**: Run `bash status.sh` or `bash logs.sh -n=100` to view recent startup or runtime errors.
- **Running automated tests**:
  ```bash
  ./.venv/bin/python -m unittest discover -s tests -v
  ```
