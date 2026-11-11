import json
from pathlib import Path
from .observation import ObservationEncoder, OBSERVATION_SIZE
from .validation import DIRECTIONS, EMPTY, START, END, PIT, BONE, validateMaze

ACTION_NAMES = ("up", "down", "left", "right")
NAME_TO_ACTION = {"up": 0, "down": 1, "left": 2, "right": 3}


def loadMaze(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class RewardConfig:
    def __init__(
        self,
        stepPenalty=-1.0,
        boneReward=5.0,
        successBonus=50.0,
        failurePenalty=-10.0,
        stepTrainReward=-0.05,
        blockedTrainPenalty=-0.12,
        newCellTrainBonus=0.12,
        boneTrainReward=1.5,
        winTrainBonus=8.0,
        timeoutTrainPenalty=0.0,
    ):
        self.stepPenalty = float(stepPenalty)
        self.boneReward = float(boneReward)
        self.successBonus = float(successBonus)
        self.failurePenalty = float(failurePenalty)
        self.stepTrainReward = float(stepTrainReward)
        self.blockedTrainPenalty = float(blockedTrainPenalty)
        self.newCellTrainBonus = float(newCellTrainBonus)
        self.boneTrainReward = float(boneTrainReward)
        self.winTrainBonus = float(winTrainBonus)
        self.timeoutTrainPenalty = float(timeoutTrainPenalty)

    def toDict(self):
        return {
            "stepPenalty": self.stepPenalty,
            "boneReward": self.boneReward,
            "successBonus": self.successBonus,
            "failurePenalty": self.failurePenalty,
        }


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
        if rewardConfig is None:
            self.rewardConfig = RewardConfig()
        elif isinstance(rewardConfig, dict):
            self.rewardConfig = RewardConfig(**rewardConfig)
        else:
            self.rewardConfig = rewardConfig
        self.encoder = ObservationEncoder(normalize=normalizeObservation)
        self.observationSize = OBSERVATION_SIZE
        self.reset()

    def inside(self, position):
        return 0 <= position[0] < self.width and 0 <= position[1] < self.height

    def reset(self):
        self.position = self.starts[0]
        self.remainingBones = set(self.bones)
        self.steps = 0
        self.done = False
        self.visited = {self.position}
        self.lastTeleported = False
        self.lastBoneCollected = False
        self.lastPitEntered = None
        self.cumulativeReward = 0.0
        self.rawCumulativeReward = 0.0
        return self.observe()

    def neighbor(self, action):
        action = self.parseAction(action)
        dx, dy, wall = DIRECTIONS[action]
        x, y = self.position
        target = (x + dx, y + dy)
        cell = self.grid[y][x]
        if bool(cell.get(wall, False)) or not self.inside(target):
            return None
        opposite = ("bottom", "top", "right", "left")[action]
        if bool(self.grid[target[1]][target[0]].get(opposite, False)):
            return None
        return target

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

    def currentScore(self):
        bonesCollected = len(self.bones) - len(self.remainingBones)
        return self.steps - 5 * bonesCollected

    def step(self, action):
        if self.done:
            raise RuntimeError("Episode already finished")
        actionIndex = self.parseAction(action)
        previousPosition = self.position
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
                self.position = self.pits[self.position]
                teleported = True

        bone = self.position in self.remainingBones
        if bone:
            self.remainingBones.remove(self.position)

        newCell = self.position not in self.visited
        self.visited.add(self.position)
        self.steps += 1
        self.lastTeleported = teleported
        self.lastBoneCollected = bone
        self.lastPitEntered = pitEntered

        won = self.position in self.ends
        timeout = (not won) and (self.steps >= self.maxSteps)
        self.done = won or timeout

        rc = self.rewardConfig
        rawReward = rc.stepPenalty
        if bone:
            rawReward += rc.boneReward
        if won:
            rawReward += rc.successBonus
        elif timeout:
            rawReward += rc.failurePenalty

        reward = (
            rc.stepTrainReward
            + (rc.blockedTrainPenalty if not moved else 0.0)
            + (rc.newCellTrainBonus if newCell else 0.0)
            + (rc.boneTrainReward if bone else 0.0)
            + (rc.winTrainBonus if won else 0.0)
            + (rc.timeoutTrainPenalty if timeout else 0.0)
        )
        self.rawCumulativeReward += float(rawReward)
        self.cumulativeReward += float(reward)

        bonesCollected = len(self.bones) - len(self.remainingBones)
        score = self.steps - 5 * bonesCollected

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
            "remainingBonesCount": len(self.remainingBones),
            "score": score,
            "done": self.done,
            "reward": float(reward),
            "rawReward": float(rawReward),
            "cumulativeReward": self.cumulativeReward,
            "rawCumulativeReward": self.rawCumulativeReward,
            "availableActions": self.availableActions(),
        }
        return self.observe(), float(reward), self.done, info

    def state(self):
        bonesCollected = len(self.bones) - len(self.remainingBones)
        return {
            "position": list(self.position),
            "steps": self.steps,
            "done": self.done,
            "won": self.position in self.ends,
            "timeout": (self.position not in self.ends) and (self.steps >= self.maxSteps),
            "bonesCollected": bonesCollected,
            "remainingBones": [list(x) for x in sorted(self.remainingBones)],
            "score": self.steps - 5 * bonesCollected,
            "cumulativeReward": round(self.cumulativeReward, 4),
            "availableActions": self.availableActions(),
            "observation": [round(float(x), 4) for x in self.observe()],
            "grid": self.grid,
        }
