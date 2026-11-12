from collections import deque
import hashlib
import json

EMPTY = 0
START = 1
END = 2
PIT = 3
BONE = 4

VALID_ELEMENTS = {EMPTY, START, END, PIT, BONE}
DIRECTIONS = ((0, -1, "top"), (0, 1, "bottom"), (-1, 0, "left"), (1, 0, "right"))
OPPOSITE_WALL = ("bottom", "top", "right", "left")
ACTION_NAMES = ("up", "down", "left", "right")
NAME_TO_ACTION = {"up": 0, "down": 1, "left": 2, "right": 3}


def computeMazeHash(mazeData):
    canonical = json.dumps(mazeData.get("grid", mazeData), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def resolvePitChain(grid, startPos):
    height = len(grid)
    width = len(grid[0]) if height else 0
    current = startPos
    visitedPits = set()
    teleported = False
    while 0 <= current[0] < width and 0 <= current[1] < height:
        cell = grid[current[1]][current[0]]
        if int(cell.get("element", 0)) != PIT:
            return current, teleported, False
        if current in visitedPits:
            return current, teleported, True
        visitedPits.add(current)
        destination = cell.get("pit_destination")
        if not isinstance(destination, dict) or "x" not in destination or "y" not in destination:
            return None, teleported, True
        nextPos = (int(destination["x"]), int(destination["y"]))
        if not (0 <= nextPos[0] < width and 0 <= nextPos[1] < height):
            return None, teleported, True
        current = nextPos
        teleported = True
    return None, teleported, True


def checkMazeSolvability(grid, requireAllBones=False):
    if not grid or not grid[0]:
        return {"solvable": False, "pathLength": -1, "reachableEnds": 0, "reachableBones": 0, "error": "Grid is empty"}
    height = len(grid)
    width = len(grid[0])
    startPos = None
    endPositions = []
    bonePositions = []
    for y in range(height):
        for x in range(width):
            element = int(grid[y][x].get("element", 0))
            if element == START:
                startPos = (x, y)
            elif element == END:
                endPositions.append((x, y))
            elif element == BONE:
                bonePositions.append((x, y))
    if startPos is None:
        return {"solvable": False, "pathLength": -1, "reachableEnds": 0, "reachableBones": 0, "error": "No Start found"}
    if not endPositions:
        return {"solvable": False, "pathLength": -1, "reachableEnds": 0, "reachableBones": 0, "error": "No End found"}

    queue = deque([(startPos, 0)])
    visited = {startPos}
    distances = {startPos: 0}

    while queue:
        (x, y), dist = queue.popleft()
        cell = grid[y][x]
        for idx, (dx, dy, wallKey) in enumerate(DIRECTIONS):
            if bool(cell.get(wallKey, False)):
                continue
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if bool(grid[ny][nx].get(OPPOSITE_WALL[idx], False)):
                continue
            resolved, _, invalidChain = resolvePitChain(grid, (nx, ny))
            if invalidChain or resolved is None:
                continue
            if resolved not in visited:
                visited.add(resolved)
                distances[resolved] = dist + 1
                queue.append((resolved, dist + 1))

    reachableEnds = [pos for pos in endPositions if pos in visited]
    reachableBones = [pos for pos in bonePositions if pos in visited]
    if not reachableEnds:
        return {"solvable": False, "pathLength": -1, "reachableEnds": 0, "reachableBones": len(reachableBones), "error": "No End is reachable"}
    if requireAllBones and len(reachableBones) < len(bonePositions):
        return {"solvable": False, "pathLength": -1, "reachableEnds": len(reachableEnds), "reachableBones": len(reachableBones), "error": "Not all bones reachable"}

    shortestEndDist = min(distances[pos] for pos in reachableEnds)
    return {
        "solvable": True,
        "pathLength": shortestEndDist,
        "reachableCells": len(visited),
        "reachableEnds": len(reachableEnds),
        "reachableBones": len(reachableBones),
        "error": "",
    }


def validateCompetitionMaze(
    mazeData,
    requireStandardSize=True,
    requireExactBones=True,
    maxBones=5,
    requireOuterWalls=True,
    requireWallSync=True,
    requireSolvable=True,
):
    errors = []
    if not isinstance(mazeData, dict) or "grid" not in mazeData:
        return {"valid": False, "errors": ["Maze data must contain a 'grid' field"]}

    grid = mazeData["grid"]
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return {"valid": False, "errors": ["Maze grid is empty"]}

    height = len(grid)
    width = len(grid[0])
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        return {"valid": False, "errors": ["Maze rows must have equal length"]}

    if requireStandardSize and (height != 10 or width != 10):
        errors.append(f"Maze grid must be 10x10, found {width}x{height}")

    startCount = 0
    endCount = 0
    boneCount = 0

    for y in range(height):
        for x in range(width):
            cell = grid[y][x]
            if not isinstance(cell, dict):
                errors.append(f"Cell at ({x}, {y}) is not a dictionary")
                continue
            try:
                element = int(cell.get("element", -1))
            except (TypeError, ValueError):
                element = -1
            if element not in VALID_ELEMENTS:
                errors.append(f"Invalid element {cell.get('element')} at ({x}, {y})")
                continue

            for wallKey in ("top", "bottom", "left", "right"):
                if wallKey not in cell:
                    errors.append(f"Missing wall key '{wallKey}' at ({x}, {y})")

            if requireOuterWalls:
                if y == 0 and not bool(cell.get("top", False)):
                    errors.append(f"Outer top boundary open at ({x}, {y})")
                if y == height - 1 and not bool(cell.get("bottom", False)):
                    errors.append(f"Outer bottom boundary open at ({x}, {y})")
                if x == 0 and not bool(cell.get("left", False)):
                    errors.append(f"Outer left boundary open at ({x}, {y})")
                if x == width - 1 and not bool(cell.get("right", False)):
                    errors.append(f"Outer right boundary open at ({x}, {y})")

            if requireWallSync:
                if x < width - 1 and isinstance(grid[y][x + 1], dict):
                    if bool(cell.get("right", False)) != bool(grid[y][x + 1].get("left", False)):
                        errors.append(f"Wall mismatch between ({x}, {y}) and ({x + 1}, {y})")
                if y < height - 1 and isinstance(grid[y + 1][x], dict):
                    if bool(cell.get("bottom", False)) != bool(grid[y + 1][x].get("top", False)):
                        errors.append(f"Wall mismatch between ({x}, {y}) and ({x}, {y + 1})")

            if element == START:
                startCount += 1
            elif element == END:
                endCount += 1
            elif element == BONE:
                boneCount += 1
            elif element == PIT:
                dest = cell.get("pit_destination")
                if dest is None or not isinstance(dest, dict) or "x" not in dest or "y" not in dest:
                    errors.append(f"Pit at ({x}, {y}) has no destination")
                else:
                    try:
                        dx, dy = int(dest["x"]), int(dest["y"])
                        if not (0 <= dx < width and 0 <= dy < height):
                            errors.append(f"Pit destination ({dx}, {dy}) outside maze")
                        elif (dx, dy) == (x, y):
                            errors.append(f"Pit at ({x}, {y}) cannot point to itself")
                        else:
                            _, _, hasCycle = resolvePitChain(grid, (x, y))
                            if hasCycle:
                                errors.append(f"Pit at ({x}, {y}) is part of a cyclic pit chain")
                    except (TypeError, ValueError):
                        errors.append(f"Pit at ({x}, {y}) has non-integer destination")

    if startCount != 1:
        errors.append(f"Maze requires exactly one start, found {startCount}")
    if endCount < 1 or endCount > 2:
        errors.append(f"Maze requires 1 or 2 ends, found {endCount}")
    if requireExactBones and boneCount != maxBones:
        errors.append(f"Maze requires exactly {maxBones} bones, found {boneCount}")
    elif boneCount > maxBones:
        errors.append(f"Maze cannot exceed {maxBones} bones, found {boneCount}")

    solvability = {"solvable": False, "pathLength": -1}
    if not errors:
        solvability = checkMazeSolvability(grid)
        if requireSolvable and not solvability["solvable"]:
            errors.append(solvability["error"] or "Maze is not solvable")

    isValid = len(errors) == 0
    return {
        "valid": isValid,
        "errors": errors,
        "solvable": solvability.get("solvable", False),
        "pathLength": solvability.get("pathLength", -1),
        "reachableBones": solvability.get("reachableBones", 0),
    }


class AuthoritativeMazeEnvironment:
    def __init__(self, mazeData, maxSteps=300, boneRewardValue=5):
        validation = validateCompetitionMaze(
            mazeData,
            requireStandardSize=False,
            requireExactBones=False,
            requireOuterWalls=False,
            requireWallSync=True,
            requireSolvable=False,
        )
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))

        self.mazeData = mazeData
        self.grid = mazeData["grid"]
        self.height = len(self.grid)
        self.width = len(self.grid[0])
        self.maxSteps = int(maxSteps)
        self.boneRewardValue = int(boneRewardValue)

        self.starts = []
        self.ends = set()
        self.bones = set()
        self.pits = {}

        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                element = int(cell["element"])
                pos = (x, y)
                if element == START:
                    self.starts.append(pos)
                elif element == END:
                    self.ends.add(pos)
                elif element == BONE:
                    self.bones.add(pos)
                elif element == PIT:
                    dest = cell["pit_destination"]
                    self.pits[pos] = (int(dest["x"]), int(dest["y"]))

        self.reset()

    def inside(self, position):
        return 0 <= position[0] < self.width and 0 <= position[1] < self.height

    def reset(self):
        self.position = self.starts[0]
        self.remainingBones = set(self.bones)
        self.steps = 0
        self.done = False
        self.won = False
        self.timeout = False
        return list(self.position)

    def parseAction(self, action):
        if isinstance(action, str):
            key = action.strip().lower()
            if key not in NAME_TO_ACTION:
                raise ValueError(f"Invalid action string '{action}'")
            return NAME_TO_ACTION[key]
        if isinstance(action, bool):
            raise ValueError("Action cannot be a boolean")
        try:
            idx = int(action)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid action value '{action}'") from exc
        if idx not in range(4):
            raise ValueError(f"Action index {idx} out of range 0..3")
        return idx

    def neighbor(self, actionIndex):
        dx, dy, wallKey = DIRECTIONS[actionIndex]
        x, y = self.position
        target = (x + dx, y + dy)
        cell = self.grid[y][x]
        if bool(cell.get(wallKey, False)) or not self.inside(target):
            return None
        if bool(self.grid[target[1]][target[0]].get(OPPOSITE_WALL[actionIndex], False)):
            return None
        return target

    def currentScore(self):
        bonesCollected = len(self.bones) - len(self.remainingBones)
        return self.steps - self.boneRewardValue * bonesCollected

    def step(self, action):
        if self.done:
            raise ValueError("Action sequence continues after episode already terminated")
        actionIndex = self.parseAction(action)
        target = self.neighbor(actionIndex)
        moved = target is not None
        if moved:
            self.position = target

        teleported = False
        if moved and self.position in self.pits:
            seenPits = set()
            while self.position in self.pits and self.position not in seenPits:
                seenPits.add(self.position)
                self.position = self.pits[self.position]
                teleported = True

        boneCollected = self.position in self.remainingBones
        if boneCollected:
            self.remainingBones.remove(self.position)

        self.steps += 1
        self.won = self.position in self.ends
        self.timeout = (not self.won) and (self.steps >= self.maxSteps)
        self.done = self.won or self.timeout
        bonesCollected = len(self.bones) - len(self.remainingBones)
        score = self.steps - self.boneRewardValue * bonesCollected

        return {
            "action": actionIndex,
            "action_name": ACTION_NAMES[actionIndex],
            "moved": moved,
            "teleported": teleported,
            "bone": boneCollected,
            "position": [self.position[0], self.position[1]],
            "steps": self.steps,
            "bones_collected": bonesCollected,
            "score": score,
            "won": self.won,
            "timeout": self.timeout,
            "done": self.done,
        }

