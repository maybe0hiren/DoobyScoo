# DoobyScoo Multiplayer Server (`dooby-scoo-server`)

The authoritative online competition backend for **DoobyScoo**. It manages player accounts, Argon2 authentication, JWT access/refresh tokens, trophy-based matchmaking, procedural competition maze generation, action-trace verification, leagues, rankings, match history, and live WebSocket notifications.

> **Architectural Boundary**: The multiplayer server **never** hosts, trains, or executes player RL models. Every player's AI Dog runs locally on their own device (`doobyscoo-agent`), and the server independently replays and verifies submitted action traces using `AuthoritativeMazeEnvironment`.

---

## 1. Directory Structure

```text
dooby-scoo-server/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── profiles.py
│   │   ├── matchmaking.py
│   │   ├── matches.py
│   │   ├── leaderboards.py
│   │   └── history.py
│   ├── core/
│   │   ├── framework.py
│   │   ├── security.py
│   │   ├── dependencies.py
│   │   ├── exceptions.py
│   │   └── websocket_manager.py
│   ├── models/
│   │   ├── user.py
│   │   ├── player_profile.py
│   │   ├── match.py
│   │   ├── maze.py
│   │   ├── result.py
│   │   └── trophy_history.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── match.py
│   │   ├── maze.py
│   │   └── leaderboard.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── matchmaking_service.py
│   │   ├── match_service.py
│   │   ├── map_generator.py
│   │   ├── result_verifier.py
│   │   ├── ranking_service.py
│   │   └── progression_service.py
│   ├── database/
│   │   ├── session.py
│   │   └── base.py
│   └── rl_verification/
│       ├── maze_environment.py
│       └── action_replay.py
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
├── requirements.txt
├── alembic.ini
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 2. Database Schema

The server manages 9 relational tables with foreign keys, unique constraints, and indexes:

1. **`users`**: `id`, `username` (UNIQUE), `email` (UNIQUE), `password_hash` (Argon2id), `display_name`, `avatar`, `settings_json`, `created_at`, `updated_at`, `last_login`.
2. **`player_profiles`**: `user_id` (PK/FK -> `users.id`), `level`, `xp`, `trophies`, `league`, `wins`, `losses`, `draws`, `best_score`, `average_score`, `total_matches`, `total_bones_collected`, `dog_model_version`, `dog_model_info`.
3. **`maps`**: `id` (PK), `version`, `difficulty` (`easy` / `medium` / `hard`), `maze_json`, `maze_hash` (SHA-256), `created_at`.
4. **`matches`**: `id` (PK), `player_1_id`, `player_2_id`, `map_id`, `map_version`, `map_hash`, `rules_json`, `status`, `verification_status`, `winner_id`, `created_at`, `started_at`, `expires_at`, `completed_at`.
5. **`match_results`**: `id` (PK), `submission_id` (UNIQUE), `match_id`, `player_id`, `action_trace`, `claimed_score`, `verified_score`, `steps`, `bones_collected`, `completed`, `final_position`, `model_version`, `verification_status`, `submitted_at` — with `UNIQUE(match_id, player_id)` to prevent duplicate accepted submissions.
6. **`trophy_history`**: `id` (PK), `player_id`, `match_id`, `previous_trophies`, `trophy_change`, `new_trophies`, `created_at` — with `UNIQUE(player_id, match_id)`.
7. **`matchmaking_queue`**: `player_id` (PK), `trophies`, `league`, `status`, `match_id`, `joined_at`, `expires_at`.
8. **`refresh_tokens`**: `token_id` (PK), `user_id`, `token_hash` (UNIQUE), `revoked`, `expires_at`, `created_at`.
9. **`ws_events`**: `event_id` (PK), `seq_id`, `user_id`, `match_id`, `event_type`, `timestamp`, `payload_json`.

---

## 3. REST API Endpoints (`/api/v1/`)

### System
- `GET /health` — Health check.
- `GET /api/v1/status` — Server status, active players, matches, and queue counts.

### Authentication
- `POST /api/v1/auth/register` — Register new account (`username`, `email`, `password`, `display_name`).
- `POST /api/v1/auth/login` — Authenticate (`username` or `email`, `password`) and receive `access_token` + `refresh_token`.
- `POST /api/v1/auth/logout` — Revoke refresh token(s).
- `POST /api/v1/auth/refresh` — Rotate refresh token and obtain a new `access_token`.
- `POST /api/v1/auth/password-reset` — Reset password (`username`, `email`, `new_password`).
- `GET /api/v1/auth/username-available?username=<name>` — Check username availability.

### Players & Profiles
- `GET /api/v1/players/me` — Retrieve authenticated player's full profile.
- `PATCH /api/v1/players/me` — Update display name, avatar, settings, or local dog model metadata.
- `GET /api/v1/players/{username}` — Retrieve public player profile (excludes private email/settings).
- `GET /api/v1/players/me/rank` — Retrieve global rank, league rank, and nearby ranked players.
- `GET /api/v1/players/me/history` — Retrieve match history and trophy history.
- `GET /api/v1/players/me/events?last_event_id=...&since_seq=...` — Recover missed events.

### Matchmaking
- `POST /api/v1/matchmaking/join` — Join competitive matchmaking queue.
- `POST /api/v1/matchmaking/cancel` — Cancel active matchmaking search.
- `GET /api/v1/matchmaking/status` — Poll current matchmaking state.

### Matches
- `GET /api/v1/matches/{match_id}` — Retrieve match status and metadata.
- `GET /api/v1/matches/{match_id}/map` — Retrieve assigned 10×10 competition maze JSON and SHA-256 hash.
- `POST /api/v1/matches/{match_id}/submit` — Submit local Dog's action trace and claimed result for server verification.
- `GET /api/v1/matches/{match_id}/result` — Retrieve official verified match result and trophy changes.
- `GET /api/v1/matches/history` — Paginated match history.

### Leaderboards
- `GET /api/v1/leaderboards/global?limit=50&offset=0` — Paginated global leaderboard.
- `GET /api/v1/leaderboards/league/{league}?limit=50&offset=0` — Paginated league leaderboard (`Beginner`, `Bronze`, `Silver`, `Gold`, `Platinum`, `Diamond`, `Master`).
- `GET /api/v1/leaderboards/leagues` — List configured leagues and trophy ranges.

---

## 4. WebSocket Protocol (`/ws`)

Connect to `ws://<host>:<port>/ws?token=<access_token>&last_event_id=<id>&since_seq=<seq>` (or send `{"type": "auth", "token": "<access_token>"}` after opening).

### Server-to-Client Events
- `connection.authenticated`
- `matchmaking.started`
- `matchmaking.opponent_found`
- `match.created`
- `match.map_assigned`
- `match.opponent_submitted`
- `match.verification_started`
- `match.completed`
- `match.expired`
- `player.profile_updated`
- `player.trophies_updated`
- `leaderboard.updated`

Every event envelope includes `event_id`, `seq_id`, `event_type`, `timestamp`, `player_id`, `match_id`, and `payload`.

---

## 5. Installation, Migrations & Startup

### Local Development
```bash
cd dooby-scoo-server
cp .env.example .env
PYTHONPATH=. ../doobyscoo-agent/.venv/bin/python -m app.main --host 0.0.0.0 --port 8000
```

### PostgreSQL + Docker Compose Deployment
```bash
cd dooby-scoo-server
cp .env.example .env
docker compose up --build -d
```

### Running Automated Tests
```bash
PYTHONPATH=dooby-scoo-server:doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m unittest discover -s dooby-scoo-server/tests -v
```

