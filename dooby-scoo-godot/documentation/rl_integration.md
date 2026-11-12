# DoobyScoo — Reinforcement Learning & Multiplayer Integration Guide

## 1. Division of Responsibility & Authoritative State Design

- **Godot (`dooby-scoo-godot`)** is responsible for visual presentation, maze creation, animations, user controls, and communicating with both the local Python RL service (`127.0.0.1:8765`) and the online multiplayer server (`127.0.0.1:8000`).
- **Python (`doobyscoo-agent`)** is the **local RL engine** running on the player's machine. It maintains the trained `RecurrentPolicy` (`models/dog.pt`), executes step-by-step recurrent inference or full competitive solves, records experiences, and performs continual PPO + rehearsal learning.
- **Multiplayer Server (`dooby-scoo-server`)** is the **authoritative online competition backend**. It never receives model weights or selects actions; instead, it distributes a canonical 10×10 competition maze to matched clients and independently replays each client's submitted `action_trace` using `AuthoritativeMazeEnvironment` to compute official scores and determine the winner.

---

## 2. Partial Observation Specification (23 Features)

The dog agent never receives the global maze layout. At each step, `ObservationEncoder` produces a 23-element `float32` vector normalized to `[0.0, 1.0]`:

| Index | Feature | Raw Values | Normalized Value |
|---|---|---|---|
| `0..3` | Neighbor cell type (**UP, DOWN, LEFT, RIGHT**) | `0=BLOCKED, 1=EMPTY, 2=BONE, 3=END, 4=PIT` | `raw / 4.0` |
| `4` | Current cell is **PIT** / just teleported | `0.0` or `1.0` | `0.0` or `1.0` |
| `5` | Current cell had **BONE** | `0.0` or `1.0` | `0.0` or `1.0` |
| `6` | Current cell is **END** | `0.0` or `1.0` | `0.0` or `1.0` |
| `7` | **Remaining Bones** ratio | `0..5` | `remaining / totalBones` |
| `8` | Current cell **Visit Count** | `0..4+` | `min(1.0, (visits - 1) / 4.0)` |
| `9..12` | Neighbor cell **Visit Counts** (**UP, DOWN, LEFT, RIGHT**) | `0..4+` (`1.0` if blocked) | `min(1.0, visits / 4.0)` |
| `13..16` | **Last Action** one-hot (**UP, DOWN, LEFT, RIGHT**) | `0.0` or `1.0` | `0.0` or `1.0` |
| `17` | **Last Move Blocked** (wall/boundary collision) | `0.0` or `1.0` | `0.0` or `1.0` |
| `18` | **Step Progress** ratio | `0..maxSteps` | `min(1.0, steps / maxSteps)` |
| `19..22` | Directed **Doorway Traversal Counts** (**UP, DOWN, LEFT, RIGHT**) | `0..3+` (`1.0` if blocked) | `min(1.0, edgeVisits / 3.0)` |

---

## 3. Local Python RL HTTP Contract (`http://127.0.0.1:8765`)

### 3.1 `GET /health`, `GET /agent/status`, and `GET /training/status`
Returns service health, model version, update count, episode statistics, and continual learning status.

### 3.2 `POST /episode/start` (also aliased at `POST /map`)
Initializes a new maze episode and resets the session's recurrent LSTM state `(h, c)`. Supports `mode: "training" | "evaluation" | "competitive"`. When `mode == "competitive"`, the latest saved checkpoint is reloaded from disk and frozen for the duration of the match.

**Request:**
```json
{
  "maze": {
    "metadata": { "maze_name": "Competition Arena" },
    "grid": []
  },
  "mode": "competitive",
  "match_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
  "deterministic": true,
  "collect_experience": false
}
```

### 3.3 `POST /episode/step` (also aliased at `POST /step`)
Selects/executes the next action, updates the recurrent LSTM state, records the transition and `action_trace`, and returns the outcome. When `done == true` in competitive mode, includes `submission_payload` ready to submit to the multiplayer server.

### 3.4 `POST /competitive/solve`
Runs a complete competitive episode on the provided maze in one call using the frozen local model and returns the full step trace and `submission_payload`:
```json
{
  "success": true,
  "session_id": "a1b2c3d4e5f6",
  "match_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
  "model_version": 8,
  "completed": true,
  "steps": 14,
  "bones_collected": 3,
  "score": -1,
  "execution_time_ms": 18,
  "action_trace": ["right", "down", "down", "right"],
  "submission_payload": {
    "completed": true,
    "steps": 14,
    "bones_collected": 3,
    "client_reported_score": -1,
    "action_trace": ["right", "down", "down", "right"],
    "execution_time_ms": 18,
    "model_version": "v8"
  }
}
```

### 3.5 `POST /competitive/learn`, `POST /episode/end`, and `POST /learn`
- `POST /competitive/learn`: Opt-in post-match continual learning on a completed competitive session (`{"session_id": "..."}`).
- `POST /episode/end` & `POST /learn`: Finalizes single-player episodes and triggers continual PPO + rehearsal updates.

---

## 4. Multiplayer Server API & WebSocket Contract (`http://127.0.0.1:8000`)

### 4.1 REST Endpoints (`/api/v1`)
- **Authentication**: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`
- **Profiles**: `GET /users/me`, `PATCH /users/me`, `GET /profiles/me`, `GET /profiles/{username}`
- **Matchmaking**: `POST /matchmaking/join`, `POST /matchmaking/leave`, `GET /matchmaking/status`
- **Matches**: `GET /matches/active`, `GET /matches/{match_id}`, `GET /matches/{match_id}/maze`, `POST /matches/{match_id}/submit`, `GET /matches/{match_id}/result`
- **Rankings & History**: `GET /leaderboards/global`, `GET /leaderboards/league/{league_name}`, `GET /leaderboards/me`, `GET /history/matches`, `GET /history/trophies`

### 4.2 WebSocket Endpoint (`/ws?token=<access_token>`)
Supports real-time push notifications (`connected`, `matchmaking_joined`, `match_found`, `match_started`, `opponent_submitted`, `match_completed`, `rating_updated`, `pong`), client `ping` heartbeats, and `sync` requests (`{"type": "sync", "last_seq": 0}`) to recover missed events after reconnection.
