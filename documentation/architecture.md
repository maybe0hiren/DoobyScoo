# DoobyScoo — System Architecture

## 1. Overview

**DoobyScoo** is a gamified Reinforcement Learning and asynchronous online multiplayer AI-vs-AI maze-solving competition platform where players create custom 10×10 mazes, train their own local AI Dog (**Dooby**) using **Recurrent Proximal Policy Optimization (Recurrent PPO)** with an LSTM memory network, and compete online in trophy-based leagues.

The platform is architected as three logically independent, cooperating components:

1. **Godot 4.6 Client (`dooby-scoo-godot/`)**: Handles the visual user interface, 10×10 maze editor, validation & BFS solvability verification, local JSON map persistence (`user://Mazes/`), animated dog character (`DogController`), scoring (`ScoreManager`), RL communication adapter (`RLAdapter`, `RLClient`, `MockRLClient`), and the **Online Multiplayer Arena** (`MultiplayerPage`, `MultiplayerClient`) with REST and WebSocket (`/ws`) integration.
2. **Local Python RL Agent (`doobyscoo-agent/`)**: Runs exclusively on each player's device. Implements the authoritative maze simulation (`MazeEnvironment`), 23-feature partial observation encoder (`ObservationEncoder`), LSTM-based Actor-Critic policy (`RecurrentPolicy`, `RecurrentState`, architecture `doobyscoo-recurrent-ppo-v2`), on-policy PPO updates (`ppo.py`), multi-map curriculum training (`BalancedMapSampler`), continuous lifelong learning with rehearsal (`RehearsalManager`, `ExperienceStore`), atomic checkpointing (`checkpoint.py`), 5-phase knowledge-transfer & retention verification (`knowledge_transfer.py`), and competitive match inference (`mode="competitive"`, `/competitive/solve`, `/competitive/learn`).
3. **Multiplayer Competition Server (`dooby-scoo-server/`)**: Independently deployed online backend managing user accounts (Argon2id + JWT access/refresh tokens), player profiles, XP/levels, trophies & 7 competitive leagues (`Beginner` through `Master`), trophy-based matchmaking, procedural 10×10 solvable competition maze generation, authoritative action-trace replay verification (`AuthoritativeMazeEnvironment`), leaderboards, match/trophy history, and real-time WebSocket notifications (`/ws`).

> **Core Privacy & Architectural Principle:** The multiplayer server never hosts, trains, or executes any player's RL model. All model weights (`models/dog.pt`) and inference remain strictly on the player's local machine; the server verifies submitted action traces against the canonical match maze.

---

## 2. Directory Structure

```text
DoobyScoo/
├── README.md
├── documentation/
│   ├── architecture.md
│   ├── maze_format.md
│   └── rl_integration.md
│
├── dooby-scoo-godot/
│   ├── project.godot
│   ├── scenes/
│   │   ├── landing_page.tscn
│   │   ├── map_editor_page.tscn
│   │   ├── my_maps.tscn
│   │   ├── mazeRow.tscn
│   │   ├── gameplay_page.tscn
│   │   ├── multiplayer_page.tscn
│   │   └── MazeSession.tscn
│   ├── Scripts/
│   │   ├── landing_page.gd
│   │   ├── map_editor_page.gd
│   │   ├── grid_map.gd
│   │   ├── my_maps.gd
│   │   ├── maze_row.gd
│   │   ├── GameplayManager.gd
│   │   ├── GameplayBoard.gd
│   │   ├── DogController.gd
│   │   ├── ScoreManager.gd
│   │   ├── MazeSession.gd
│   │   ├── MazeSerializer.gd
│   │   ├── MazeValidator.gd
│   │   ├── MazeSolver.gd
│   │   ├── DoobyScooAgentClient.gd
│   │   ├── ai_integration/
│   │   │   ├── RLAdapter.gd
│   │   │   ├── RLClient.gd
│   │   │   └── MockRLClient.gd
│   │   └── multiplayer/
│   │       ├── MultiplayerClient.gd
│   │       └── MultiplayerPage.gd
│   └── assets/
│       ├── backgroundImages/
│       └── starter_maps/
│
├── doobyscoo-agent/
│   ├── requirements.txt
│   ├── README.md
│   ├── doobyscoo/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── server.py
│   │   ├── environment/
│   │   ├── agent/
│   │   ├── training/
│   │   ├── evaluation/
│   │   ├── communication/
│   │   └── storage/
│   ├── maps/
│   │   ├── train/
│   │   ├── validation/
│   │   ├── test/
│   │   └── played/
│   ├── models/
│   │   └── dog.pt
│   └── tests/
│
└── dooby-scoo-server/
    ├── README.md
    ├── requirements.txt
    ├── Dockerfile
    ├── docker-compose.yml
    ├── alembic.ini
    ├── .env.example
    ├── migrations/
    ├── app/
    │   ├── main.py
    │   ├── config.py
    │   ├── database/
    │   ├── models/
    │   ├── schemas/
    │   ├── api/
    │   ├── services/
    │   ├── rl_verification/
    │   └── core/
    └── tests/
```

---

## 3. Component Responsibilities

### 3.1 Godot Client (`dooby-scoo-godot/`)

- **`MazeSession.gd` (Autoload)**: Stores session state across scene transitions (`loaded_maze`, `editing_path`, `selected_mode`, `deterministic_eval`, `collect_experience`, `server_url`, `multiplayer_server_url`, `profile_slot`) and supports multi-client launch flags (`--rl-url=`, `--server-url=`, `--profile-slot=`).
- **`MultiplayerClient.gd` & `MultiplayerPage.gd`**: Provides full account registration/login, persistent JWT session management (`user://auth_session_<slot>.json`), live WebSocket connection (`/ws`), matchmaking queue controls, embedded `GameplayBoard` for watching local Dog execution on the server's competition maze, result submission, global & league leaderboards, match/trophy history, and post-match local learning trigger.
- **`grid_map.gd`, `map_editor_page.gd`, `MazeValidator.gd`, `MazeSolver.gd`, & `MazeSerializer.gd`**: Interactive 10×10 grid editor, structural validation, BFS solvability verification, and local JSON serialization.
- **`GameplayManager.gd`, `GameplayBoard.gd`, `DogController.gd`, & `ScoreManager.gd`**: Renders the active maze, animates dog movements, and computes scores (`Score = Steps - 5 * Bones Collected`).

### 3.2 Local Python RL Agent (`doobyscoo-agent/`)

- **`MazeEnvironment` & `ObservationEncoder`**: Authoritative simulation and 23-feature partial observation encoding (4-neighbor cell types, current cell indicators, remaining bones ratio, current/neighbor visitation counts, last action one-hot, wall-collision flag, step progress, and directed doorway traversal counts).
- **`RecurrentPolicy` & `RecurrentState`**: PyTorch Actor-Critic network (`doobyscoo-recurrent-ppo-v2`) with shared relational directional scoring, `nn.LSTM` memory core, 4-action policy head, scalar value head, and auxiliary neighbor/revisit prediction heads.
- **`SessionManager` (`communication/session_manager.py`)**: Supports both training/evaluation episodes and frozen-model competitive match episodes (`mode="competitive"`, `/competitive/solve`, `/competitive/learn`), recording the full `action_trace` and `submission_payload` while rejecting any payload containing sensitive credentials (`password`, `refresh_token`).

### 3.3 Authoritative Multiplayer Server (`dooby-scoo-server/`)

- **`auth_service.py` & `core/security.py`**: Argon2id password hashing, JWT access/refresh tokens, and refresh token revocation.
- **`matchmaking_service.py` & `map_generator.py`**: Trophy-window matchmaking (preventing self-matches and expanding range over wait time) and procedural 10×10 solvable competition maze generation with SHA-256 verification.
- **`rl_verification/action_replay.py` & `services/result_verifier.py`**: Independently replays submitted action traces step-by-step on the server's canonical maze copy, computes official scores, and rejects malformed, oversized, or duplicate submissions.
- **`services/match_service.py` & `progression_service.py`**: Evaluates winner by completion status → lower official score → fewer steps → more bones → faster execution time, updates trophies (`+25` win, `-15` loss clamped at `0`, `+5` draw), XP, levels, and league assignments, and broadcasts real-time WebSocket events.
