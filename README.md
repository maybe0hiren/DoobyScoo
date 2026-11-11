# DoobyScoo — Gamified Reinforcement Learning Maze Platform

**DoobyScoo** is an interactive, gamified Reinforcement Learning platform where players design custom 10×10 mazes (with walls, collectible bones, teleporting pits, and goal flags) in **Godot 4.6** and watch an AI-controlled dog (**Dooby**) learn to solve them using **Recurrent PPO (LSTM Actor-Critic)** in **Python / PyTorch**.

---

## Project Structure

- **`dooby-scoo-godot/`**: Complete Godot 4.6 game application:
  - **Landing Page (`scenes/landing_page.tscn`)**: Main menu with animated dog mascot, **My Maps**, **Create Maze**, and **Play / Train Dog**.
  - **Maze Editor (`scenes/map_editor_page.tscn`)**: Interactive 10×10 grid editor with Start, End, Pit (drag-to-destination), Bone placement, synchronized wall handles, dirty-state tracking, `MazeValidator`, and BFS `MazeSolver`.
  - **My Maps (`scenes/my_maps.tscn`)**: Browse, Play/Train, Edit, and Delete saved mazes in `user://Mazes/` (pre-seeded with 3 starter mazes on first launch).
  - **Gameplay & Training Page (`scenes/gameplay_page.tscn`)**: Watch Dooby navigate the maze with smooth animations, live step/bone/score tracking (`Score = Steps - 5 × Bones`), Mode A (Training + Continual Learning), Mode B (Evaluation), and a clearly labeled offline `MockRLClient` fallback.
- **`doobyscoo-agent/`**: Complete Python Recurrent PPO RL system:
  - `doobyscoo/environment/`: `MazeEnvironment`, 8-feature partial `ObservationEncoder`, and `validateMaze` / `checkSolvability`.
  - `doobyscoo/agent/`: `RecurrentPolicy`, `RecurrentState`, and clipped BPTT `ppo.py`.
  - `doobyscoo/training/`: `trainer.py`, `rollout.py`, `BalancedMapSampler`, `RehearsalManager`, and `TrainingMetricsTracker`.
  - `doobyscoo/evaluation/`: `evaluator.py` and `comparison.py`.
  - `doobyscoo/communication/`: Local HTTP server (`server.py`), `GameService` (`session_manager.py`), and `protocol.py`.
  - `doobyscoo/storage/`: Atomic checkpointing (`checkpoint.py`) and `ExperienceStore` (`experience_store.py`).
- **`documentation/`**:
  - [Architecture Overview](documentation/architecture.md)
  - [Maze JSON Format](documentation/maze_format.md)
  - [RL Integration Contract](documentation/rl_integration.md)

---

## Quick Start

### 1. Start the Python RL Service
```bash
cd doobyscoo-agent
./.venv/bin/python -m doobyscoo serve --model models/dog.pt --port 8765
```

### 2. Run the Godot Game
Open `dooby-scoo-godot/project.godot` in **Godot 4.6** and press **Run Project (F5)**.
- If the Python server is running on `127.0.0.1:8765`, Gameplay connects automatically in **Mode A (Training)** or **Mode B (Evaluation)**.
- If you run the Godot project without starting the Python server, the Gameplay screen gracefully offers to switch to the **Mock Testing Client** so you can still preview all UI and animations offline.

### 3. Train, Evaluate, and Test from Terminal
```bash
cd doobyscoo-agent

# Run all automated tests
./.venv/bin/python -m unittest discover -s tests -v

# Evaluate on unseen test maps
./.venv/bin/python -m doobyscoo evaluate --maps maps/test --model models/dog.pt --compare-untrained

# Check checkpoint & server status
./.venv/bin/python -m doobyscoo status --model models/dog.pt --port 8765
```
