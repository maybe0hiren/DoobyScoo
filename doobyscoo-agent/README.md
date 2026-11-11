# DoobyScoo Agent — Continuous Reinforcement Learning System

`doobyscoo-agent` is the PyTorch-based Recurrent Proximal Policy Optimization (Recurrent PPO) reinforcement learning backend for **DoobyScoo**.

## Features

- **8-Feature Partial Observation**: Encodes only local directional neighbors (`UP`, `DOWN`, `LEFT`, `RIGHT` as `BLOCKED`, `EMPTY`, `BONE`, `END`, `PIT`), current cell flags, and normalized remaining bones.
- **LSTM Actor-Critic (`RecurrentPolicy` & `RecurrentState`)**: Maintains recurrent hidden state `(h, c)` and relative trajectory memory across steps within each episode.
- **Multi-Map Curriculum Training (`BalancedMapSampler`)**: Trains across 30+ mazes with exposure and difficulty balancing.
- **Continuous Lifelong Learning & Rehearsal (`RehearsalManager`, `ExperienceStore`)**: Collects trajectories from newly played maps in Godot, stores new maps in `maps/played/`, mixes fresh on-policy rehearsal rollouts from `maps/train/` and `maps/played/` (strictly excluding `maps/test/` and `maps/validation/`), and updates `models/dog.pt` atomically with `.bak` backups.

---

## CLI Commands

Run commands from the `doobyscoo-agent/` directory using the virtual environment (`.venv/bin/python`):

### 1. Initial Training
```bash
./.venv/bin/python -m doobyscoo train \
    --maps maps/train \
    --val-maps maps/validation \
    --model models/dog.pt \
    --updates 200 \
    --episodes 8 \
    --max-steps 300
```

### 2. Resume Training
```bash
./.venv/bin/python -m doobyscoo train \
    --maps maps/train \
    --model models/dog.pt \
    --updates 50 \
    --resume
```

### 3. Evaluate on Unseen Test Maps
```bash
./.venv/bin/python -m doobyscoo evaluate \
    --maps maps/test \
    --model models/dog.pt \
    --max-steps 300
```

Compare against an untrained baseline:
```bash
./.venv/bin/python -m doobyscoo evaluate \
    --maps maps/test \
    --model models/dog.pt \
    --compare-untrained
```

### 4. Start the Local HTTP Agent Server (for Godot)
```bash
./.venv/bin/python -m doobyscoo serve \
    --model models/dog.pt \
    --maps maps/played \
    --train-maps maps/train \
    --val-maps maps/validation \
    --port 8765
```

### 5. Check Model & Server Status
```bash
./.venv/bin/python -m doobyscoo status --model models/dog.pt --port 8765
```

### 6. Run Automated Test Suite
```bash
./.venv/bin/python -m unittest discover -s tests -v
```

