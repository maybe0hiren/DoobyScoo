import json
from pathlib import Path
from ..config import DEFAULT_CONFIG
from .observation import ObservationEncoder, OBSERVATION_SIZE
from .validation import DIRECTIONS, EMPTY, START, END, PIT, BONE, validateMaze

ACTION_NAMES = ("up", "down", "left", "right")
NAME_TO_ACTION = {"up": 0, "down": 1, "left": 2, "right": 3}
OPPOSITE_WALL = ("bottom", "top", "right", "left")


def loadMaze(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class RewardConfig:
    """RL training reward. Independent from the official score (steps - 5 * bones)."""

    FIELDS = tuple(DEFAULT_CONFIG["reward"].keys())

    def __init__(self, **overrides):
        values = dict(DEFAULT_CONFIG["reward"])
        unknown = set(overrides) - set(values)
        if unknown:
            raise ValueError(f"Unknown reward config fields: {sorted(unknown)}")
        values.update(overrides)
        for key, value in values.items():
            setattr(self, key, float(value))

    @classmethod
    def coerce(cls, value):
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(**value)
        raise TypeError("rewardConfig must be None, a dict or a RewardConfig")

    def revisitPenaltyFor(self, priorVisits):
        """Penalty for entering a square that was already visited `priorVisits` (>=1) times."""
        if priorVisits <= 0:
            return 0.0
        penalty = self.revisitPenalty + self.repeatedRevisitPenalty * (priorVisits - 1)
        return max(self.maxRevisitPenalty, penalty)

    def toDict(self):
        return {key: getattr(self, key) for key in self.FIELDS}


class MazeEnvironment:
    def __init__(self, mazeData, maxSteps=300, rewardConfig=None, normalizeObservation=True):
        if not isinstance(mazeData, dict) or "grid" not in mazeData:
            raise ValueError("Maze data must contain a 'grid' field")
        self.mazeData = mazeData
        self.grid = mazeData["grid"]
        self.height = len(self.grid) if isinstance(self.grid, list) else 0
        if not self.height or not isinstance(self.grid[0], list) or not self.grid[0]:
            raise ValueError("Maze grid is empty")
        self.width = len(self.grid[0])
        if any(not isinstance(row, list) or len(row) != self.width for row in self.grid):
            raise ValueError("Maze rows must have equal length")

        self.starts = []
        self.ends = set()
        self.bones = set()
        self.pits = {}

        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if not isinstance(cell, dict) or "element" not in cell:
                    raise ValueError(f"Invalid cell at ({x}, {y})")
                element = int(cell["element"])
                if element not in (EMPTY, START, END, PIT, BONE):
                    raise ValueError(f"Invalid element {element} at ({x}, {y})")
                position = (x, y)
                if element == START:
                    self.starts.append(position)
                elif element == END:
                    self.ends.add(position)
                elif element == BONE:
                    self.bones.add(position)
                elif element == PIT:
                    destination = cell.get("pit_destination")
                    if destination is None or not isinstance(destination, dict) or "x" not in destination or "y" not in destination:
                        raise ValueError(f"Pit {position} has no destination")
                    target = (int(destination["x"]), int(destination["y"]))
                    if not self.inside(target):
                        raise ValueError(f"Pit destination {target} outside maze")
                    if target == position:
                        raise ValueError(f"Pit {position} cannot point to itself")
                    self.pits[position] = target

        if len(self.starts) != 1 or not (1 <= len(self.ends) <= 2):
            raise ValueError("Maze requires exactly one start and 1 or 2 ends")
        if len(self.bones) > 5:
            raise ValueError(f"Maze cannot have more than 5 bones, found {len(self.bones)}")

        validation = validateMaze(mazeData, requireWallSync=True)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))

        self.maxSteps = int(maxSteps)
        self.rewardConfig = RewardConfig.coerce(rewardConfig)
        self.encoder = ObservationEncoder(normalize=normalizeObservation)
        self.observationSize = OBSERVATION_SIZE
        self._neighborCache = {}
        self.reset()

    def inside(self, position):
        return 0 <= position[0] < self.width and 0 <= position[1] < self.height

    def reset(self):
        self.position = self.starts[0]
        self.remainingBones = set(self.bones)
        self.steps = 0
        self.done = False
        # Per-episode visitation memory. visitCounts tracks squares the dog came to
        # rest on (pit destinations included); pit squares stepped on and directed
        # doorway traversals are tracked so the dog remembers explored branches.
        self.visitCounts = {self.position: 1}
        self.pitVisitCounts = {}
        self.edgeCounts = {}
        self.revisits = 0
        self.wallBumps = 0
        self.lastAction = None
        self.lastMoved = True
        self.lastTeleported = False
        self.lastBoneCollected = False
        self.lastPitEntered = None
        self.cumulativeReward = 0.0
        self.rawCumulativeReward = 0.0
        return self.observe()

    @property
    def visited(self):
        return set(self.visitCounts)

    def visitCountAt(self, position):
        return self.visitCounts.get(position, 0) + self.pitVisitCounts.get(position, 0)

    def neighborAt(self, position, action):
        key = (position, action)
        if key in self._neighborCache:
            return self._neighborCache[key]
        dx, dy, wall = DIRECTIONS[action]
        x, y = position
        target = (x + dx, y + dy)
        result = target
        if bool(self.grid[y][x].get(wall, False)) or not self.inside(target):
            result = None
        elif bool(self.grid[target[1]][target[0]].get(OPPOSITE_WALL[action], False)):
            result = None
        self._neighborCache[key] = result
        return result

    def neighbor(self, action):
        return self.neighborAt(self.position, self.parseAction(action))

    def availableActions(self):
        return [ACTION_NAMES[a] for a in range(4) if self.neighbor(a) is not None]

    def availableActionIndices(self):
        return [a for a in range(4) if self.neighbor(a) is not None]

    def parseAction(self, action):
        if isinstance(action, str):
            key = action.strip().lower()
            if key not in NAME_TO_ACTION:
                raise ValueError(f"Unknown action string: {action}")
            return NAME_TO_ACTION[key]
        actionIndex = int(action)
        if actionIndex not in range(4):
            raise ValueError("Action must be 0..3")
        return actionIndex

    def observe(self):
        return self.encoder.encode(self)

    def observeRaw(self):
        return self.encoder.encodeRaw(self)

    def bonesCollected(self):
        return len(self.bones) - len(self.remainingBones)

    def currentScore(self):
        return self.steps - 5 * self.bonesCollected()

    def step(self, action):
        if self.done:
            raise RuntimeError("Episode already finished")
        actionIndex = self.parseAction(action)
        previousPosition = self.position
        edgeKey = (previousPosition, actionIndex)
        self.edgeCounts[edgeKey] = self.edgeCounts.get(edgeKey, 0) + 1

        target = self.neighbor(actionIndex)
        moved = target is not None
        if moved:
            self.position = target
        teleported = False
        pitEntered = None
        if moved and self.position in self.pits:
            pitEntered = list(self.position)
            seenPits = set()
            while self.position in self.pits and self.position not in seenPits:
                seenPits.add(self.position)
                self.pitVisitCounts[self.position] = self.pitVisitCounts.get(self.position, 0) + 1
                self.position = self.pits[self.position]
                teleported = True

        bone = self.position in self.remainingBones
        if bone:
            self.remainingBones.remove(self.position)

        priorVisits = 0
        if moved:
            priorVisits = self.visitCounts.get(self.position, 0)
            self.visitCounts[self.position] = priorVisits + 1
            if priorVisits > 0:
                self.revisits += 1
        else:
            self.wallBumps += 1
        newCell = moved and priorVisits == 0
        revisit = moved and priorVisits > 0

        self.steps += 1
        self.lastAction = actionIndex
        self.lastMoved = moved
        self.lastTeleported = teleported
        self.lastBoneCollected = bone
        self.lastPitEntered = pitEntered

        won = self.position in self.ends
        timeout = (not won) and (self.steps >= self.maxSteps)
        self.done = won or timeout

        rc = self.rewardConfig
        breakdown = {"move": rc.movePenalty}
        if not moved:
            breakdown["wall"] = rc.wallPenalty
        if newCell:
            breakdown["novelty"] = rc.noveltyReward
        if revisit:
            breakdown["revisit"] = rc.revisitPenaltyFor(priorVisits)
        if bone:
            breakdown["bone"] = rc.boneReward
            if not self.remainingBones and self.bones:
                breakdown["allBones"] = rc.allBonesBonus
        if won:
            breakdown["end"] = rc.endReward
        elif timeout:
            breakdown["stepLimit"] = rc.stepLimitPenalty
            breakdown["failure"] = rc.failurePenalty
        reward = float(sum(breakdown.values()))

        # Official-score-aligned signal (negated score delta) kept for reporting only.
        rawReward = -1.0 + (5.0 if bone else 0.0)
        self.rawCumulativeReward += rawReward
        self.cumulativeReward += reward

        bonesCollected = self.bonesCollected()
        info = {
            "action": actionIndex,
            "actionName": ACTION_NAMES[actionIndex],
            "previousPosition": list(previousPosition),
            "position": list(self.position),
            "pitEntered": pitEntered,
            "moved": moved,
            "teleported": teleported,
            "bone": bone,
            "won": won,
            "timeout": timeout,
            "steps": self.steps,
            "bonesCollected": bonesCollected,
            "totalBones": len(self.bones),
            "remainingBonesCount": len(self.remainingBones),
            "score": self.steps - 5 * bonesCollected,
            "done": self.done,
            "newCell": newCell,
            "revisit": revisit,
            "visitCount": self.visitCounts.get(self.position, 0),
            "wallBump": not moved,
            "revisits": self.revisits,
            "wallBumps": self.wallBumps,
            "uniqueCells": len(self.visitCounts),
            "reward": reward,
            "rewardBreakdown": breakdown,
            "rawReward": rawReward,
            "cumulativeReward": self.cumulativeReward,
            "rawCumulativeReward": self.rawCumulativeReward,
            "availableActions": self.availableActions(),
        }
        return self.observe(), reward, self.done, info

    def state(self):
        bonesCollected = self.bonesCollected()
        return {
            "position": list(self.position),
            "steps": self.steps,
            "done": self.done,
            "won": self.position in self.ends,
            "timeout": (self.position not in self.ends) and (self.steps >= self.maxSteps),
            "bonesCollected": bonesCollected,
            "remainingBones": [list(x) for x in sorted(self.remainingBones)],
            "score": self.steps - 5 * bonesCollected,
            "revisits": self.revisits,
            "uniqueCells": len(self.visitCounts),
            "cumulativeReward": round(self.cumulativeReward, 4),
            "availableActions": self.availableActions(),
            "observation": [round(float(x), 4) for x in self.observe()],
            "grid": self.grid,
        }
