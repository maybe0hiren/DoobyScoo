# DoobyScoo — Gamified Reinforcement Learning & Online Competitive Maze Platform

**DoobyScoo** is a gamified Reinforcement Learning maze platform and asynchronous AI-vs-AI online competitive game built with **Godot 4.6**, **PyTorch (Recurrent PPO / LSTM Actor-Critic)**, and an authoritative **Multiplayer Backend Server**.

Every player owns, trains, and operates their own AI Dog locally on their device. When ready, players enter online matchmaking, receive identical server-generated competition mazes, watch their local AI Dog solve the maze, and submit their action traces to the authoritative server for independent replay verification, trophy progression, league advancement, and global leaderboard rankings.

---

## 1. Overall Three-Component Architecture

```text
DoobyScoo/
├── dooby-scoo-godot/      # Godot 4.6 Client (Maze Editor, Single-Player Training, Multiplayer Arena UI)
├── doobyscoo-agent/       # Local Python RL Agent (PyTorch Recurrent PPO, Local Inference & Continual Learning)
├── dooby-scoo-server/     # Authoritative Online Multiplayer Backend (Accounts, Matchmaking, Replay Verification, Leagues)
└── documentation/         # Detailed Architecture, Maze Format & RL Integration Docs
```

### Division of Responsibilities

1. **Godot Client (`dooby-scoo-godot/`)**:
   - Visual 10×10 Maze Editor, Maze Validator, BFS Solvability Checker, and Local Map Manager (`user://Mazes/`).
   - Single-player AI Dog training and evaluation visualizer.
   - Online Multiplayer client: authentication, player profiles, matchmaking, live WebSocket event handling (`/ws`), passing assigned competition maps to the local Python RL agent, animating the Dog locally, and submitting action traces to the server.
2. **Local Python RL Agent (`doobyscoo-agent/`)**:
   - Runs locally on each player's device (`127.0.0.1:8765`).
   - 8-feature partial observation encoder (`[UP, DOWN, LEFT, RIGHT, isPit, isBone, isEnd, remainingBonesNorm]`).
   - Recurrent PPO (`LSTMCell` + directional memory head) trained across 32 training maps and 6 validation maps, achieving **87.5% win rate** on unseen test maps.
   - Executes competitive inference locally with frozen weights during matches, records the exact `action_trace`, and supports optional post-match continual learning.
3. **Multiplayer Server (`dooby-scoo-server/`)**:
   - Independently deployable backend (`http://0.0.0.0:8000` + `ws://0.0.0.0:8000/ws`).
   - Manages user accounts (Argon2id password hashing, JWT access tokens, revocable refresh tokens), player profiles, XP, levels, trophies, and 7 leagues (`Beginner` through `Master`).
   - Generates, validates, and hashes 10×10 solvable competition mazes (`SHA-256`).
   - Independently replays every submitted `action_trace` in `AuthoritativeMazeEnvironment` to verify wall collisions, pit teleports, bone collection, completion, and official score ($\text{Score} = \text{Steps} - 5 \times \text{Bones Collected}$, lower is better).
   - Never hosts, stores, or executes player RL models.

---

## 2. Multiplayer Competition Workflow

1. **Authentication**: Player registers or logs in via Godot (`POST /api/v1/auth/register` or `/login`) and establishes an authenticated WebSocket connection (`WS /ws`).
2. **Matchmaking**: Player clicks **Find Competitive Match** (`POST /api/v1/matchmaking/join`). The server pairs players with similar trophy counts and emits `matchmaking.opponent_found`, `match.created`, and `match.map_assigned`.
3. **Map Distribution**: Both clients fetch the assigned competition maze (`GET /api/v1/matches/{match_id}/map`), receiving the exact same 10×10 maze JSON and SHA-256 `map_hash`.
4. **Local AI Execution**: Each player's Godot client sends the competition maze to its local `doobyscoo-agent` (`127.0.0.1:8765`). The local RL Dog solves the maze on the player's device while keeping its policy fixed.
5. **Result Submission & Authoritative Replay**: Each client submits its `action_trace` and claimed metrics (`POST /api/v1/matches/{match_id}/submit`). The server replays every step in `AuthoritativeMazeEnvironment`, rejects any fabricated or mismatched claims, and computes the official score.
6. **Winner Determination & Progression**:
   - Completed Dog beats incomplete Dog.
   - Among completed Dogs, lower official score ($\text{Steps} - 5 \times \text{Bones}$) wins.
   - Equal scores break ties by fewer steps; identical performance results in an official Draw.
   - Trophies (`+25` win, `-15` loss clamped at `0`, `+5` draw), XP (`+25` participation, `+50` win, `+30` personal best, `+100` league promotion), leagues, and leaderboards update atomically inside a database transaction, and `match.completed` is pushed over WebSockets.

---

## 3. Quick Start — Running Everything Locally

### Step 1: Start the Multiplayer Server (`port 8000`)
```bash
PYTHONPATH=dooby-scoo-server ./doobyscoo-agent/.venv/bin/python -m app.main --host 127.0.0.1 --port 8000
```

### Step 2: Start Local Python RL Agent(s)
For a single local player (`port 8765`):
```bash
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m doobyscoo serve --model doobyscoo-agent/models/dog.pt --port 8765
```

To run **two independent local players** on the same computer, start a second RL agent on `port 8766`:
```bash
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m doobyscoo serve --model doobyscoo-agent/models/dog.pt --port 8766
```

### Step 3: Launch Godot Client(s)
```bash
# Player 1 Client
godot --path ./dooby-scoo-godot -- --profile-slot=p1 --rl-url=http://127.0.0.1:8765 --server-url=http://127.0.0.1:8000

# Player 2 Client
godot --path ./dooby-scoo-godot -- --profile-slot=p2 --rl-url=http://127.0.0.1:8766 --server-url=http://127.0.0.1:8000
```

---

## 4. Production Deployment (Docker + PostgreSQL)

```bash
cd dooby-scoo-server
cp .env.example .env
# Edit .env to set a strong JWT_SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build -d
```

For internet deployment on a VPS or homelab, place Nginx/Caddy in front of `dooby-scoo-server:8000` with TLS so Godot clients connect over `https://` and `wss://`.

---

## 5. Automated Verification & Tests

Run both the RL agent test suite (23 tests) and the multiplayer server & end-to-end two-player test suite (12 tests):

```bash
# 1. RL Agent Unit, Integration & Acceptance Tests
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m unittest discover -s doobyscoo-agent/tests -v

# 2. Multiplayer Server & Two-Player End-to-End Tests
PYTHONPATH=dooby-scoo-server:doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m unittest discover -s dooby-scoo-server/tests -v
```

---

## 6. Security Limitations & Future Improvements

- **Anti-Cheat Scope**: Server-side action replay guarantees that every verified score is legally achievable on the exact assigned competition maze (`SHA-256` verified) within `max_steps`. However, deterministic action replay cannot cryptographically prove that an action sequence was produced by a neural network rather than a custom solver or human script. Future iterations can incorporate signed execution enclaves or statistical behavioral attestation.
