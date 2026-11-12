# DoobyScoo Python RL Agent (`doobyscoo-agent`)

The local Reinforcement Learning package for **DoobyScoo**. Each player runs `doobyscoo-agent` locally on their device to train their own **Recurrent PPO (Direction-Equivariant LSTM Actor-Critic)** Dog model (`models/dog.pt`), retain knowledge across previously encountered mazes via on-policy rehearsal, and execute competitive maze solving during online multiplayer matches.

> **Privacy & Competitive Boundary**: Your RL model weights (`models/dog.pt`) never leave your device, and the local RL agent never receives account passwords or refresh tokens. During an active competitive match, the agent loads the latest saved model, freezes the policy for the duration of the match, executes recurrent inference locally, and returns the resulting `action_trace` and `submission_payload` to Godot.

---

## 1. Package Structure

```text
doobyscoo-agent/
├── config/
│   └── training_config.json       # Centralized reward, exploration, PPO & rehearsal config
├── doobyscoo/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py                  # Default configuration + entropy & reward schedules
│   ├── server.py
│   ├── environment/
│   │   ├── validation.py
│   │   ├── observation.py         # 23-feature partial observation + episodic visit memory
│   │   └── maze_environment.py    # Configurable rewards, revisit penalties & pit visit tracking
│   ├── agent/
│   │   ├── recurrent_state.py     # Per-episode LSTM hidden state (h, c)
│   │   ├── network.py             # Direction-equivariant RecurrentPolicy (doobyscoo-recurrent-ppo-v2)
│   │   └── ppo.py                 # Multi-horizon GAE + Recurrent PPO + directional utility learner
│   ├── training/
│   │   ├── rollout.py             # Vectorised multi-maze rollout collector
│   │   ├── curriculum.py          # Shuffled-deck BalancedMapSampler with struggle slots
│   │   ├── rehearsal.py           # Fresh on-policy RehearsalManager (excludes test/val by path & hash)
│   │   ├── metrics.py             # Full training telemetry (wins, score, bones, revisits, unique cells, entropy)
│   │   └── trainer.py             # Fresh training, resume, adaptive retention & checkpointing
│   ├── evaluation/
│   │   ├── evaluator.py           # Deterministic per-map & aggregate evaluation
│   │   ├── comparison.py          # Baseline & checkpoint comparison
│   │   └── knowledge_transfer.py  # 5-phase knowledge-transfer, retention & generalization verifier
│   ├── storage/
│   │   ├── checkpoint.py          # Atomic save/load, best checkpoint & strict lineage checks
│   │   └── experience_store.py    # Played-map deduplication & hash-level test-map isolation
│   └── communication/
│       ├── protocol.py
│       ├── session_manager.py
│       └── server.py
├── maps/
│   ├── train/       # 32 training mazes
│   ├── validation/  # 6 validation mazes
│   ├── test/        # 8 held-out test mazes (never used in training or rehearsal)
│   └── played/      # Locally played mazes for continual rehearsal
├── models/
│   ├── dog.pt                     # Latest validated RecurrentPolicy checkpoint
│   ├── dog_best.pt                # Best evaluation checkpoint
│   ├── dog_metrics.jsonl          # Per-update training telemetry log
│   └── knowledge_transfer_report.json
└── tests/
```

---

## 2. Partial Observation Space (23 Features)

The Dog never sees the global maze or shortest-path hints. At every step, `ObservationEncoder` produces a normalized 23-element `float32` vector in `[0.0, 1.0]`:

| Indices | Feature | Encoding |
|---|---|---|
| `0..3` | Adjacent neighbour type (`UP, DOWN, LEFT, RIGHT`) | `0=BLOCKED, 1=EMPTY, 2=BONE, 3=END, 4=PIT` divided by `4.0` |
| `4` | Current square is Pit / just teleported | `0.0` or `1.0` |
| `5` | Bone collected on current square | `0.0` or `1.0` |
| `6` | Current square is End | `0.0` or `1.0` |
| `7` | Remaining bones ratio | `remainingBones / totalBones` |
| `8..11` | Neighbour visit level (`UP, DOWN, LEFT, RIGHT`) | `min(visits, 4) / 4.0` (`0.0` = unexplored, `0.25` = once, `0.50` = twice, `1.0` = 4+; `0` if blocked) |
| `12` | Current square visit level | `min(visits, 4) / 4.0` |
| `13..16` | Doorway traversal level from current square (`UP, DOWN, LEFT, RIGHT`) | `min(edgeVisits, 4) / 4.0` |
| `17..20` | Previous action one-hot (`UP, DOWN, LEFT, RIGHT`) | `0.0` or `1.0` (all zeros at step 0) |
| `21` | Previous action bumped into a wall | `0.0` or `1.0` |
| `22` | Elapsed step ratio | `steps / maxSteps` |

---

## 3. Centralized Reward & Exploration Configuration

Configured in `doobyscoo/config.py` and `config/training_config.json` (while keeping the official game score formula `Official Score = Steps - 5 * Bones Collected` untouched):

- **Ordinary movement (`movePenalty`)**: `-0.04`
- **Novelty bonus (`noveltyReward`)**: `+0.08` (awarded only on the first visit to a square in an episode)
- **Bone collection (`boneReward`)**: `+3.50` (once per Bone; ~88× the movement cost) + `allBonesBonus`: `+2.00` when all Bones in the maze are collected
- **Reaching an End (`endReward`)**: `+10.00`
- **Revisit penalty (`revisitPenalty` / `repeatedRevisitPenalty` / `maxRevisitPenalty`)**: `-0.08` on first revisit, `-0.04` per additional prior visit, capped at `-0.24` so necessary backtracking out of dead ends remains preferable to wall collisions
- **Wall collision (`wallPenalty`)**: `-0.60` (on top of `movePenalty`)
- **Step limit / failed episode (`stepLimitPenalty` / `failurePenalty`)**: `-2.00` / `-3.00`

---

## 4. CLI Commands

### Start Fresh Training from Scratch
```bash
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m doobyscoo train \
    --fresh \
    --maps doobyscoo-agent/maps/train \
    --val-maps doobyscoo-agent/maps/validation \
    --model doobyscoo-agent/models/dog.pt \
    --updates 40 \
    --episodes 16 \
    --max-steps 300
```

### Resume Training Later
```bash
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m doobyscoo train \
    --resume \
    --maps doobyscoo-agent/maps/train \
    --rehearsal doobyscoo-agent/maps/played \
    --val-maps doobyscoo-agent/maps/validation \
    --model doobyscoo-agent/models/dog.pt \
    --updates 20 \
    --episodes 16 \
    --max-steps 300
```

### Evaluate on Unseen Test Maps (with Untrained Baseline Comparison)
```bash
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m doobyscoo evaluate \
    --maps doobyscoo-agent/maps/test \
    --model doobyscoo-agent/models/dog.pt \
    --compare-untrained
```

### Run the 5-Phase Knowledge-Transfer & Retention Experiment
```bash
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m doobyscoo transfer-eval \
    --train-maps doobyscoo-agent/maps/train \
    --test-maps doobyscoo-agent/maps/test \
    --phase1-updates 25 \
    --phase2-updates 20 \
    --report doobyscoo-agent/models/knowledge_transfer_report.json
```

### Start Local RL Service (for Godot Single-Player & Multiplayer)
```bash
PYTHONPATH=doobyscoo-agent ./doobyscoo-agent/.venv/bin/python -m doobyscoo serve \
    --model doobyscoo-agent/models/dog.pt \
    --maps doobyscoo-agent/maps/played \
    --train-maps doobyscoo-agent/maps/train \
    --val-maps doobyscoo-agent/maps/validation \
    --port 8765
```
