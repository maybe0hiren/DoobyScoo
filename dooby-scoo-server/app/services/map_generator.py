import json
import random
import uuid
from ..core.security import nowIso
from ..models.maze import MazeMapModel
from ..rl_verification.maze_environment import (
    BONE,
    EMPTY,
    END,
    PIT,
    START,
    checkMazeSolvability,
    computeMazeHash,
    validateCompetitionMaze,
)


def _createAllWallsGrid(width=10, height=10):
    grid = []
    for _ in range(height):
        row = []
        for _ in range(width):
            row.append({
                "element": EMPTY,
                "top": True,
                "bottom": True,
                "left": True,
                "right": True,
                "pit_destination": None,
                "visited": False,
            })
        grid.append(row)
    return grid


def _openPassage(grid, x1, y1, x2, y2):
    if x2 == x1 + 1 and y2 == y1:
        grid[y1][x1]["right"] = False
        grid[y2][x2]["left"] = False
    elif x2 == x1 - 1 and y2 == y1:
        grid[y1][x1]["left"] = False
        grid[y2][x2]["right"] = False
    elif y2 == y1 + 1 and x2 == x1:
        grid[y1][x1]["bottom"] = False
        grid[y2][x2]["top"] = False
    elif y2 == y1 - 1 and x2 == x1:
        grid[y1][x1]["top"] = False
        grid[y2][x2]["bottom"] = False


def generateCompetitionMaze(difficulty="medium", seed=None, version=1):
    rng = random.Random(seed)
    diff = str(difficulty or "medium").lower()
    if diff not in ("easy", "medium", "hard"):
        diff = "medium"

    extraOpenProb = {"easy": 0.45, "medium": 0.28, "hard": 0.15}[diff]
    pitCountTarget = {"easy": 1, "medium": 1, "hard": 2}[diff]
    endCountTarget = 2 if diff == "easy" else 1

    for _ in range(40):
        width, height = 10, 10
        grid = _createAllWallsGrid(width, height)

        visited = {(0, 0)}
        stack = [(0, 0)]
        while stack:
            cx, cy = stack[-1]
            neighbors = []
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                    neighbors.append((nx, ny))
            if neighbors:
                nx, ny = rng.choice(neighbors)
                _openPassage(grid, cx, cy, nx, ny)
                visited.add((nx, ny))
                stack.append((nx, ny))
            else:
                stack.pop()

        for y in range(height):
            for x in range(width):
                if x < width - 1 and rng.random() < extraOpenProb:
                    _openPassage(grid, x, y, x + 1, y)
                if y < height - 1 and rng.random() < extraOpenProb:
                    _openPassage(grid, x, y, x, y + 1)

        startPos = (0, 0)
        grid[startPos[1]][startPos[0]]["element"] = START

        farCandidates = [
            (x, y)
            for y in range(height)
            for x in range(width)
            if (x + y) >= 10 and (x, y) != startPos
        ]
        rng.shuffle(farCandidates)
        ends = farCandidates[:endCountTarget]
        for ex, ey in ends:
            grid[ey][ex]["element"] = END

        usedCells = {startPos} | set(ends)
        availableCells = [
            (x, y)
            for y in range(height)
            for x in range(width)
            if (x, y) not in usedCells
        ]
        rng.shuffle(availableCells)

        bones = availableCells[:5]
        for bx, by in bones:
            grid[by][bx]["element"] = BONE
            usedCells.add((bx, by))

        remainingForPits = [c for c in availableCells[5:] if c not in usedCells]
        if len(remainingForPits) >= pitCountTarget * 2:
            for idx in range(pitCountTarget):
                pitCell = remainingForPits[idx]
                destCell = remainingForPits[pitCountTarget + idx]
                px, py = pitCell
                dx, dy = destCell
                grid[py][px]["element"] = PIT
                grid[py][px]["pit_destination"] = {"x": int(dx), "y": int(dy)}
                usedCells.add(pitCell)

        mazeId = f"comp_{diff}_{uuid.uuid4().hex[:10]}"
        mazeData = {
            "metadata": {
                "maze_name": mazeId,
                "author": "DoobyScoo Competition Server",
                "difficulty": diff,
                "version": int(version),
                "created_at": nowIso(),
            },
            "grid": grid,
        }

        validation = validateCompetitionMaze(
            mazeData,
            requireStandardSize=True,
            requireExactBones=True,
            maxBones=5,
            requireOuterWalls=True,
            requireWallSync=True,
            requireSolvable=True,
        )
        solvability = checkMazeSolvability(grid, requireAllBones=True)
        if validation["valid"] and solvability["solvable"]:
            mazeHash = computeMazeHash(mazeData)
            mazeData["metadata"]["map_hash"] = mazeHash
            return {
                "id": mazeId,
                "version": int(version),
                "difficulty": diff,
                "mazeJson": mazeData,
                "mazeHash": mazeHash,
                "pathLength": solvability["pathLength"],
            }

    raise RuntimeError("Failed to generate a valid solvable competition maze")


def difficultyForTrophies(avgTrophies):
    tVal = int(avgTrophies or 0)
    if tVal < 600:
        return "easy"
    if tVal < 1600:
        return "medium"
    return "hard"


def createAndStoreMap(db, difficulty="medium", seed=None, version=1):
    generated = generateCompetitionMaze(difficulty=difficulty, seed=seed, version=version)
    createdAt = nowIso()
    db.execute(
        """
        INSERT INTO maps (id, version, difficulty, maze_json, maze_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            generated["id"],
            generated["version"],
            generated["difficulty"],
            json.dumps(generated["mazeJson"], sort_keys=True),
            generated["mazeHash"],
            createdAt,
        ),
    )
    return MazeMapModel(
        id=generated["id"],
        version=generated["version"],
        difficulty=generated["difficulty"],
        mazeJson=generated["mazeJson"],
        mazeHash=generated["mazeHash"],
        createdAt=createdAt,
    )


def getMapById(db, mapId):
    row = db.fetchOne("SELECT * FROM maps WHERE id = ?", (str(mapId),))
    return MazeMapModel.fromRow(row)

