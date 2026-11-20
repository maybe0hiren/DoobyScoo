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
│   │   ├── observation.py         # 38-feature partial observation (local + visit memory + 5 Bone locations)
│   │   └── maze_environment.py    # Score limit 100, revisit schedule (0,-2,-4,-6,-8) & Bone schedule (-10..-20)
│   ├── agent/
│   │   ├── recurrent_state.py     # Per-episode LSTM hidden state (h, c)
│   │   ├── network.py             # Direction-equivariant RecurrentPolicy (doobyscoo-recurrent-ppo-v3)
│   │   └── ppo.py                 # Multi-horizon GAE + Recurrent PPO + directional utility learner
│   ├── training/
│   │   ├── rollout.py             # Vectorised multi-maze & repeated-attempt rollout collector
│   │   ├── curriculum.py          # Shuffled-deck BalancedMapSampler with struggle slots
│   │   ├── rehearsal.py           # Fresh on-policy RehearsalManager (excludes test/val by path & hash)
│   │   ├── metrics.py             # MazeOptimizationTracker, LearningProgressReporter & training telemetry
│   │   └── trainer.py             # optimizeMaze(), fresh training, resume, adaptive retention & checkpointing
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

## 2. Partial Observation Space (38 Features)

The Dog never sees the global wall grid, pit locations, or shortest-path hints, but is given knowledge of all five Bone locations from the start of the episode. At every step, `ObservationEncoder` produces a normalized 38-element `float32` vector (`[0.0, 1.0]` for indices `0..22` and `[-1.0, 1.0]` for relative Bone displacements at `23..37`):

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
| `23..37` | 5 Bone slots (`(dxNorm, dyNorm, isCollected)` × 5) | `dxNorm = (boneX - dogX) / max(1, width - 1)`, `dyNorm = (boneY - dogY) / max(1, height - 1)` (`0.0` once collected), `isCollected` in `{0.0, 1.0}` |

---

## 3. Centralized Reward, Score Limit & Exploration Configuration

Configured in `doobyscoo/config.py` and `config/training_config.json` (while keeping the official multiplayer score formula `Official Score = Steps - 5 * Bones Collected` untouched):

- **Training Score & Maximum Score Limit (`maxScoreLimit = 100`)**:
  - `Training Score = Steps + totalBoneScoreReduction` (`+1` per step; `-10` for Bones 1..4; `-20` for the 5th Bone).
  - Scores `<= 100` (including `99` and `100`) are allowed; if `trainingScore > 100` (`>= 101`), the episode terminates immediately as failed (`scoreLimitPenalty = -15.0`, `failurePenalty = -10.0`), the failed trajectory is included in on-policy PPO updates, and a fresh attempt starts automatically.
- **Revisit Penalty Schedule (`firstVisitPenalty`, `revisitPenalty`, `repeatedRevisitPenalty`, `maxRevisitPenalty`)**:
  - 1st visit: `0`, 2nd visit: `-2`, 3rd visit: `-4`, 4th visit: `-6`, 5th+ visits: `-8` (capped at `-8`).
- **Bone Collection Schedule (`boneScoreReduction`, `fifthBoneScoreReduction`, `boneReward`, `fifthBoneReward`)**:
  - Bones 1..4: `-10` training score reduction (`+10.0` RL reward) each.
  - 5th Bone (completing all 5): `-20` training score reduction (`+20.0` RL reward; total `-60` score reduction / `+60.0` reward for all 5 Bones).
- **Ordinary movement (`movePenalty`)**: `-0.50` + **Novelty bonus (`noveltyReward`)**: `+1.50` on first visit
- **Reaching an End (`endReward`)**: `+25.00`
- **Wall collision (`wallPenalty`)**: `-12.00`

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
