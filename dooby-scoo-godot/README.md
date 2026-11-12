# DoobyScoo Godot Client (`dooby-scoo-godot`)

The **Godot 4.6** game client for **DoobyScoo**. It provides the visual 10×10 Maze Editor, My Maps browser, single-player AI Dog training/evaluation arena, and the full **Online Multiplayer Competitive Arena**.

---

## 1. Key Screens & Scenes

- **Landing Page (`scenes/landing_page.tscn`, `Scripts/landing_page.gd`)**:
  - **My Maps**: Browse, play/train, edit, or delete saved mazes.
  - **Create Maze**: Open the 10×10 visual Maze Editor.
  - **Play / Train Dog**: Watch and train your local AI Dog on custom or starter mazes.
  - **Multiplayer Arena**: Connect to the online multiplayer server, manage your profile, enter matchmaking, compete on server-generated mazes, and climb the leaderboards.
- **Maze Editor (`scenes/map_editor_page.tscn`, `Scripts/map_editor_page.gd`, `Scripts/grid_map.gd`)**:
  - Place Start (1), End (1–2), Bones (up to 5), Pits (drag-to-target destination), and synchronized walls.
  - Validates mazes (`Scripts/MazeValidator.gd`) and checks solvability (`Scripts/MazeSolver.gd`) before saving to `user://Mazes/` (`Scripts/MazeSerializer.gd`).
- **Single-Player Gameplay (`scenes/gameplay_page.tscn`, `Scripts/GameplayManager.gd`, `Scripts/GameplayBoard.gd`)**:
  - Connects to the local Python RL service (`http://127.0.0.1:8765`) via `RLAdapter.gd` and `RLClient.gd`.
- **Online Multiplayer Arena (`scenes/multiplayer_page.tscn`, `Scripts/multiplayer/MultiplayerPage.gd`, `Scripts/multiplayer/MultiplayerClient.gd`)**:
  - Account registration, login, token refresh, and persistent session storage (`user://multiplayer_session_<slot>.json`).
  - Live WebSocket connection (`/ws`) with heartbeats, auto-reconnect, missed-event recovery, and duplicate-event filtering.
  - Competitive matchmaking (`SEARCHING` -> `OPPONENT_FOUND` -> `MATCH_CREATED` -> `MAP_ASSIGNED` -> `DOG SOLVING LOCALLY` -> `WAITING FOR OPPONENT` -> `VERIFYING` -> `COMPLETED`).
  - Embedded `GameplayBoard` where your local AI Dog solves the competition maze locally on your device.
  - Global Leaderboard, League Leaderboard (`Beginner` through `Master`), Nearby Rankings, Match History, Trophy History, and Post-Match Local Continual Learning.

---

## 2. Running Two Local Clients Simultaneously

You can run two separate Godot client instances on the same machine, each connected to its own local Python RL agent and its own player account:

```bash
# Client 1 (connected to local RL agent on 8765, profile slot p1)
godot --path ./dooby-scoo-godot -- --profile-slot=p1 --rl-url=http://127.0.0.1:8765 --server-url=http://127.0.0.1:8000

# Client 2 (connected to local RL agent on 8766, profile slot p2)
godot --path ./dooby-scoo-godot -- --profile-slot=p2 --rl-url=http://127.0.0.1:8766 --server-url=http://127.0.0.1:8000
```

