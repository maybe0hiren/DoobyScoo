# DoobyScoo — Maze JSON Format Specification

## 1. Storage Location

- **Godot User Maps**: `user://Mazes/<MazeName>.json`
- **Python RL Datasets**:
  - `doobyscoo-agent/maps/train/`: Initial training maps (32 maps)
  - `doobyscoo-agent/maps/validation/`: Validation maps (6 maps)
  - `doobyscoo-agent/maps/test/`: Held-out unseen evaluation maps (8 maps)
  - `doobyscoo-agent/maps/played/`: User-created/played maps collected during gameplay

---

## 2. Top-Level JSON Schema

```json
{
  "metadata": {
    "maze_name": "Starter Meadow Run",
    "author": "Player",
    "created_at": "2026-11-11T14:30:00",
    "editor_version": 1,
    "grid_size": 10
  },
  "grid": [
    [
      {
        "element": 0,
        "top": true,
        "bottom": false,
        "left": true,
        "right": false,
        "pit_destination": null,
        "visited": false
      }
    ]
  ]
}
```

---

## 3. Coordinate and Indexing Convention

- **Grid Dimensions**: 10 rows × 10 columns (100 cells total).
- **Indexing**: `grid[y][x]` where:
  - `y` is the **row** index (`0` = top row, `9` = bottom row).
  - `x` is the **column** index (`0` = leftmost column, `9` = rightmost column).

---

## 4. Cell Properties

Each cell object in `grid[y][x]` contains:

| Field | Type | Description |
|---|---|---|
| `element` | `int` | Cell element type (`0..4`, see table below). |
| `top` | `bool` | Whether a wall blocks movement upward (`y - 1`). Must be `true` when `y == 0`. |
| `bottom` | `bool` | Whether a wall blocks movement downward (`y + 1`). Must be `true` when `y == 9`. |
| `left` | `bool` | Whether a wall blocks movement leftward (`x - 1`). Must be `true` when `x == 0`. |
| `right` | `bool` | Whether a wall blocks movement rightward (`x + 1`). Must be `true` when `x == 9`. |
| `pit_destination` | `null` or `{"x": int, "y": int}` | Target coordinates when `element == 3` (`PIT`); `null` for all other elements. |
| `visited` | `bool` | Editor/runtime helper flag (default `false`). |

### Element Constants

| Value | Constant | Description |
|---|---|---|
| `0` | `EMPTY` | Standard passable floor cell. |
| `1` | `START` | Dog starting cell. Exactly **1** required per maze. |
| `2` | `END` | Goal cell. **1 or 2** required per maze. |
| `3` | `PIT` | Teleportation pit. Immediately transports the dog to `pit_destination`. |
| `4` | `BONE` | Collectible bone reward. Up to **5** per maze (reduces effective step score by 5 each). |

---

## 5. Validation & Solvability Rules

1. **Wall Synchronization**:
   - `grid[y][x]["right"] == grid[y][x + 1]["left"]` for all `0 <= x < 9`.
   - `grid[y][x]["bottom"] == grid[y + 1][x]["top"]` for all `0 <= y < 9`.
2. **Outer Boundaries**:
   - Top row (`y == 0`) has `top = true`.
   - Bottom row (`y == 9`) has `bottom = true`.
   - Left column (`x == 0`) has `left = true`.
   - Right column (`x == 9`) has `right = true`.
3. **Pit Integrity**:
   - Every Pit (`element == 3`) must have a non-null `pit_destination` dictionary `{"x": target_x, "y": target_y}` within `0..9`.
   - A Pit cannot point to itself (`target != (x, y)`), and chained Pits cannot form an infinite cycle.
4. **Solvability**:
   - At least one `END` cell and all placed `BONE` cells must be reachable from `START` via valid moves and Pit transitions.
