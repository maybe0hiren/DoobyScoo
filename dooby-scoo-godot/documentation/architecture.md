# DoobyScoo — System Architecture

## 1. Overview

**DoobyScoo** is a gamified Reinforcement Learning platform where players create custom 10×10 mazes with walls, collectible bones, teleporting pits, and goal markers, and watch an AI-controlled dog (**Dooby**) learn to solve them using **Recurrent Proximal Policy Optimization (Recurrent PPO)** with an LSTM memory network.

The platform is architected as two decoupled, cooperating subsystems:

1. **Godot 4.6 Application (`dooby-scoo-godot/`)**: Handles the visual user interface, maze editor, validation & BFS solvability verification, local JSON map persistence (`user://Mazes/`), animated dog character (`DogController`), scoring (`ScoreManager`), and RL communication adapter (`RLAdapter`, `RLClient`, `MockRLClient`).
2. **Python RL System (`doobyscoo-agent/`)**: Implements the authoritative maze simulation (`MazeEnvironment`), 8-feature partial observation encoder (`ObservationEncoder`), LSTM-based Actor-Critic policy (`RecurrentPolicy`, `RecurrentState`), on-policy PPO updates (`ppo.py`), multi-map curriculum training (`BalancedMapSampler`), continuous lifelong learning with rehearsal (`RehearsalManager`, `ExperienceStore`), atomic checkpointing (`checkpoint.py`), evaluation & model comparison (`evaluator.py`, `comparison.py`), and the local HTTP server (`server.py`, `session_manager.py`).

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
│   │   └── ai_integration/
│   │       ├── RLAdapter.gd
│   │       ├── RLClient.gd
│   │       └── MockRLClient.gd
│   └── assets/
│       ├── backgroundImages/
│       └── starter_maps/
│
└── doobyscoo-agent/
    ├── requirements.txt
    ├── README.md
    ├── doobyscoo/
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── server.py
    │   ├── environment/
    │   │   ├── maze_environment.py
    │   │   ├── observation.py
    │   │   └── validation.py
    │   ├── agent/
    │   │   ├── network.py
    │   │   ├── recurrent_state.py
    │   │   └── ppo.py
    │   ├── training/
    │   │   ├── trainer.py
    │   │   ├── rollout.py
    │   │   ├── rehearsal.py
    │   │   ├── curriculum.py
    │   │   └── metrics.py
    │   ├── evaluation/
    │   │   ├── evaluator.py
    │   │   └── comparison.py
    │   ├── communication/
    │   │   ├── server.py
    │   │   ├── session_manager.py
    │   │   └── protocol.py
    │   └── storage/
    │       ├── checkpoint.py
    │       └── experience_store.py
    ├── maps/
    │   ├── train/
    │   ├── validation/
    │   ├── test/
    │   └── played/
    ├── models/
    │   └── dog.pt
    └── tests/
        ├── test_environment.py
        ├── test_observation.py
        ├── test_agent.py
        ├── test_training.py
        ├── test_continual_learning.py
        └── test_integration.py
```

---

## 3. Component Responsibilities

### 3.1 Godot Application Components

- **`MazeSession.gd` (Autoload)**: Stores session state across scene transitions (`loaded_maze`, `editing_path`, `selected_mode`, `deterministic_eval`, `collect_experience`, `server_url`) and seeds starter mazes into `user://Mazes/` on first run.
- **`grid_map.gd` & `map_editor_page.gd`**: Interactive 10×10 grid editor supporting Start, End, Pit (drag-to-target destination), Bone placement, synchronized wall toggling, and dirty-state tracking.
- **`MazeValidator.gd`**: Checks structural validity (1 Start, 1–2 Ends, ≤5 Bones, valid Pit destinations without cycles, blocked outer boundaries, synchronized internal walls).
- **`MazeSolver.gd`**: Deterministic BFS solvability verifier that respects walls, boundaries, and Pit teleportation chains to confirm at least one End and all placed Bones are reachable before saving or training.
- **`MazeSerializer.gd`**: Handles safe JSON serialization and deserialization (`Vector2i` ↔ `{"x": int, "y": int}`) and file storage in `user://Mazes/`.
- **`ScoreManager.gd`**: Independently computes the official game score:
  $$\text{Score} = \text{Steps} - 5 \times \text{Bones Collected}$$
- **`GameplayManager.gd`, `GameplayBoard.gd`, & `DogController.gd`**: Renders the active maze, animates the dog's movements, bone pickups, wall bumps, and pit teleports, and coordinates step execution through `RLAdapter`.
- **`RLAdapter.gd`, `RLClient.gd`, & `MockRLClient.gd`**: Isolates HTTP communication with the Python RL server and provides a clearly labeled offline `MockRLClient` for UI testing when the Python service is not running.

### 3.2 Python RL Components

- **`MazeEnvironment` (`environment/maze_environment.py`)**: Authoritative simulation matching Godot's exact coordinate convention (`x = col`, `y = row`, `grid[y][x]`), wall blocking, Pit chain teleportation, Bone collection, and End termination.
- **`ObservationEncoder` (`environment/observation.py`)**: Encodes strictly local 8-feature observations (4 directional neighbors: UP, DOWN, LEFT, RIGHT as `BLOCKED=0, EMPTY=1, BONE=2, END=3, PIT=4` normalized to `[0, 1]`, plus current-cell Pit/Bone/End flags and normalized remaining bones).
- **`RecurrentPolicy` & `RecurrentState` (`agent/network.py`, `agent/recurrent_state.py`)**: PyTorch Actor-Critic network with feature encoder, `nn.LSTMCell`, 4-action policy head, scalar value head, and per-episode recurrent state tracking.
- **`Continual Learning & Rehearsal` (`training/trainer.py`, `training/rehearsal.py`, `storage/experience_store.py`)**: Records on-policy trajectories from every played map, saves newly encountered maps to `maps/played/` (strictly excluding `maps/test` and `maps/validation`), mixes fresh on-policy rehearsal rollouts from `maps/train` and `maps/played`, performs clipped Recurrent PPO updates, and atomically updates `models/dog.pt` (with `.bak` backup).
