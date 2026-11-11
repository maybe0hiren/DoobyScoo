# DoobyScoo — Reinforcement Learning Integration Guide

## 1. Division of Responsibility & Authoritative State Design

- **Godot (`dooby-scoo-godot`)** is responsible for the visual presentation, maze creation, animations, and user controls.
- **Python (`doobyscoo-agent`)** is the **authoritative source of environment transitions and RL decisions** during live sessions (while also validating any `reported_position` sent by Godot to detect discrepancies).
- When Godot requests a step, Python selects an action using its `RecurrentPolicy` and per-session `RecurrentState`, executes the transition in `MazeEnvironment`, records the experience in the session trajectory, and returns the action and resulting state so Godot can animate the movement, bone collection, pit teleportation, and completion banner with zero state drift.

---

## 2. Partial Observation Specification (8 Features)

The dog agent never receives the global maze layout. At each step, `ObservationEncoder` produces an 8-element `float32` vector normalized to `[0.0, 1.0]`:

| Index | Feature | Raw Values | Normalized Value |
|---|---|---|---|
| `0` | Neighbor **UP** `(0, -1)` | `0=BLOCKED, 1=EMPTY, 2=BONE, 3=END, 4=PIT` | `raw / 4.0` |
| `1` | Neighbor **DOWN** `(0, +1)` | `0=BLOCKED, 1=EMPTY, 2=BONE, 3=END, 4=PIT` | `raw / 4.0` |
| `2` | Neighbor **LEFT** `(-1, 0)` | `0=BLOCKED, 1=EMPTY, 2=BONE, 3=END, 4=PIT` | `raw / 4.0` |
| `3` | Neighbor **RIGHT** `(+1, 0)` | `0=BLOCKED, 1=EMPTY, 2=BONE, 3=END, 4=PIT` | `raw / 4.0` |
| `4` | Current cell is **PIT** / just teleported | `0.0` or `1.0` | `0.0` or `1.0` |
| `5` | Current cell had **BONE** | `0.0` or `1.0` | `0.0` or `1.0` |
| `6` | Current cell is **END** | `0.0` or `1.0` | `0.0` or `1.0` |
| `7` | **Remaining Bones** ratio | `0..5` | `remaining / totalBones` |

---

## 3. HTTP Communication Contract (`http://127.0.0.1:8765`)

### 3.1 `GET /health`
Checks whether the Python RL service is running.
```json
{
  "status": "ok",
  "service": "doobyscoo-agent",
  "learning": false
}
```

### 3.2 `GET /agent/status` and `GET /training/status`
Returns model version, update count, episode statistics, and continual learning status.
```json
{
  "status": "ok",
  "modelVersion": 6,
  "updates": 30,
  "totalEpisodes": 240,
  "totalSteps": 14820,
  "bestWinRate": 1.0,
  "bestScore": 30.2,
  "learning": false,
  "activeSessions": 1,
  "playedMapsCount": 3,
  "pendingEpisodes": 0
}
```

### 3.3 `POST /episode/start` (also aliased at `POST /map`)
Initializes a new maze episode and resets the session's recurrent LSTM state `(h, c)`.

**Request:**
```json
{
  "maze": {
    "metadata": { "maze_name": "Starter Meadow Run" },
    "grid": []
  },
  "mode": "training",
  "deterministic": false,
  "collect_experience": true
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "a1b2c3d4e5f6",
  "mode": "training",
  "deterministic": false,
  "collect_experience": true,
  "model_version": 6,
  "observation": [0.25, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 1.0],
  "available_actions": ["up", "right"],
  "state": {
    "position": [3, 9],
    "steps": 0,
    "done": false,
    "won": false,
    "bonesCollected": 0,
    "remainingBones": [[1, 2], [4, 5], [6, 1], [7, 8], [8, 3]],
    "score": 0
  }
}
```

### 3.4 `POST /agent/action`
Queries the policy for an action given the current session and observation without advancing the environment.

**Request:**
```json
{
  "session_id": "a1b2c3d4e5f6",
  "observation": [0.25, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 1.0],
  "deterministic": false
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "a1b2c3d4e5f6",
  "action": 3,
  "action_name": "right",
  "log_prob": -0.312,
  "value": 4.82,
  "done": false,
  "available_actions": ["up", "right"],
  "model_version": 6
}
```

### 3.5 `POST /episode/step` (also aliased at `POST /step`)
Selects/executes the next action, updates the recurrent LSTM state, records the transition, and returns the outcome. When `done == true`, automatically finalizes the episode and triggers continual learning if enabled.

**Request:**
```json
{
  "session_id": "a1b2c3d4e5f6",
  "deterministic": false,
  "reported_position": [3, 9]
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "a1b2c3d4e5f6",
  "action": 3,
  "action_name": "right",
  "previousPosition": [3, 9],
  "position": [4, 9],
  "moved": true,
  "teleported": false,
  "bone": true,
  "won": false,
  "timeout": false,
  "steps": 1,
  "bonesCollected": 1,
  "score": -4,
  "done": false,
  "reward": 1.57,
  "observation": [0.25, 0.0, 0.25, 0.25, 0.0, 1.0, 0.0, 0.8],
  "state": {}
}
```

### 3.6 `POST /episode/end` and `POST /learn`
- `POST /episode/end`: Explicitly marks an episode complete, stores the trajectory in `ExperienceStore`, saves the map to `maps/played/`, and schedules background PPO + rehearsal updates.
- `POST /learn`: Triggers an immediate continual learning cycle combining recent gameplay trajectories with fresh on-policy rehearsal episodes from `maps/train/` and `maps/played/`.
