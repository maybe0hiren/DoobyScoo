import json
import random
from pathlib import Path
import numpy as np

DIRECTIONS = ((0, -1, "top"), (0, 1, "bottom"), (-1, 0, "left"), (1, 0, "right"))


def loadMaze(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class MazeEnvironment:
    def __init__(self, mazeData, maxSteps=300):
        self.mazeData = mazeData
        self.grid = mazeData["grid"]
        self.height = len(self.grid)
        if not self.height or not self.grid[0]:
            raise ValueError("Maze grid is empty")
        self.width = len(self.grid[0])
        if any(len(row) != self.width for row in self.grid):
            raise ValueError("Maze rows must have equal length")
        self.starts = []
        self.ends = set()
        self.bones = set()
        self.pits = {}
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                element = int(cell["element"])
                position = (x, y)
                if element == 1:
                    self.starts.append(position)
                elif element == 2:
                    self.ends.add(position)
                elif element == 4:
                    self.bones.add(position)
                elif element == 3:
                    destination = cell.get("pit_destination")
                    if destination is None:
                        raise ValueError(f"Pit {position} has no destination")
                    target = (int(destination["x"]), int(destination["y"]))
                    if not self.inside(target):
                        raise ValueError(f"Pit destination {target} outside maze")
                    self.pits[position] = target
        if len(self.starts) != 1 or not self.ends:
            raise ValueError("Maze requires exactly one start and at least one end")
        self.maxSteps = maxSteps
        self.reset()

    def inside(self, position):
        return 0 <= position[0] < self.width and 0 <= position[1] < self.height

    def reset(self):
        self.position = self.starts[0]
        self.remainingBones = set(self.bones)
        self.steps = 0
        self.done = False
        self.visited = {self.position}
        return self.observe()

    def neighbor(self, action):
        dx, dy, wall = DIRECTIONS[action]
        x, y = self.position
        target = (x + dx, y + dy)
        cell = self.grid[y][x]
        if bool(cell[wall]) or not self.inside(target):
            return None
        opposite = ("bottom", "top", "right", "left")[action]
        if bool(self.grid[target[1]][target[0]][opposite]):
            return None
        return target

    def observe(self):
        features = []
        for action in range(4):
            target = self.neighbor(action)
            kind = 0 if target is None else (3 if target in self.ends else 2 if target in self.remainingBones else 4 if target in self.pits else 1)
            features.extend([float(kind == value) for value in range(5)])
        features.append(len(self.remainingBones) / max(1, len(self.bones)))
        features.append(min(1.0, self.steps / self.maxSteps))
        return np.asarray(features, dtype=np.float32)

    def step(self, action):
        if self.done:
            raise RuntimeError("Episode already finished")
        action = int(action)
        if action not in range(4):
            raise ValueError("Action must be 0..3")
        target = self.neighbor(action)
        moved = target is not None
        if moved:
            self.position = target
        teleported = False
        if moved:
            seenPits = set()
            while self.position in self.pits and self.position not in seenPits:
                seenPits.add(self.position)
                self.position = self.pits[self.position]
                teleported = True
        bone = self.position in self.remainingBones
        if bone:
            self.remainingBones.remove(self.position)
        newCell = self.position not in self.visited
        self.visited.add(self.position)
        self.steps += 1
        won = self.position in self.ends
        timeout = self.steps >= self.maxSteps
        self.done = won or timeout
        reward = -0.05 - (0.12 if not moved else 0) + (0.12 if newCell else 0) + (1.5 if bone else 0) + (8.0 if won else 0)
        info = {
            "position": list(self.position), "moved": moved, "teleported": teleported,
            "bone": bone, "won": won, "timeout": timeout,
            "steps": self.steps, "bonesCollected": len(self.bones) - len(self.remainingBones),
            "score": self.steps - 5 * (len(self.bones) - len(self.remainingBones)),
            "done": self.done, "reward": reward,
        }
        return self.observe(), reward, self.done, info

    def state(self):
        return {
            "position": list(self.position), "steps": self.steps, "done": self.done,
            "remainingBones": [list(x) for x in sorted(self.remainingBones)],
            "score": self.steps - 5 * (len(self.bones) - len(self.remainingBones)),
            "grid": self.grid,
        }
