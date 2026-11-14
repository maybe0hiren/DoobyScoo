import json
from pathlib import Path
from ..config import DEFAULT_CONFIG
from .observation import (
    ACTION_MASK_OFFSET,
    BONE_FEATURES_PER_SLOT,
    BONE_OBSERVATION_OFFSET,
    EXPLORATION_MEMORY_OFFSET,
    LOCAL_VIEW_CENTER,
    LOCAL_VIEW_CENTER_INDEX,
    LOCAL_VIEW_OFFSET,
    LOCAL_VIEW_RADIUS,
    LOCAL_VIEW_SIDE,
    LOCAL_VIEW_SIZE,
    MAX_BONES,
    NAVIGATION_OFFSET,
    OBJECTIVE_OFFSET,
    OBSERVATION_SIZE,
    OBS_BLOCKED,
    OBS_BONE,
    OBS_EMPTY,
    OBS_END,
    OBS_PIT,
    OBS_UNKNOWN,
    ObservationEncoder,
)
from .validation import DIRECTIONS, EMPTY, START, END, PIT, BONE, validateMaze

ACTION_NAMES = ("up", "down", "left", "right")
NAME_TO_ACTION = {"up": 0, "down": 1, "left": 2, "right": 3}
OPPOSITE_WALL = ("bottom", "top", "right", "left")
OPPOSITE_ACTION_INDEX = (1, 0, 3, 2)


def loadMaze(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class RewardConfig:
    """RL training reward and training score rules.

    Official multiplayer score (Steps - 5 * Bones Collected) is completely
    separate and never modified by RewardConfig.
    """

    FIELDS = tuple(DEFAULT_CONFIG["reward"].keys())

    def __init__(self, **overrides):
        values = dict(DEFAULT_CONFIG["reward"])
        unknown = set(overrides) - set(values)
        if unknown:
            raise ValueError(f"Unknown reward config fields: {sorted(unknown)}")
        values.update(overrides)
        if "boneReward" in overrides and "fifthBoneReward" not in overrides:
            if "allBonesBonus" in overrides:
                values["fifthBoneReward"] = float(values["boneReward"]) + float(values["allBonesBonus"])
            else:
                values["fifthBoneReward"] = 2.0 * float(values["boneReward"])
        if "boneScoreReduction" in overrides and "fifthBoneScoreReduction" not in overrides:
            values["fifthBoneScoreReduction"] = 2.0 * float(values["boneScoreReduction"])
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
        """Return training penalty when entering a cell with `priorVisits` prior visits.
        - 1st visit (priorVisits == 0): 0
        - 2nd visit (priorVisits == 1): revisitPenalty (-2)
        - 3rd visit (priorVisits == 2): revisitPenalty + repeatedRevisitPenalty (-4)
        - 4th visit (priorVisits == 3): revisitPenalty + 2 * repeatedRevisitPenalty (-6)
        - 5th+ visit (priorVisits >= 4): capped at maxRevisitPenalty (-8)
        """
        if priorVisits <= 0:
            return float(self.firstVisitPenalty)
        penalty = float(self.revisitPenalty) + float(self.repeatedRevisitPenalty) * (int(priorVisits) - 1)
        return max(float(self.maxRevisitPenalty), penalty)

    def revisitPenaltyForVisit(self, visitNumber):
        """Return training penalty by 1-based visit number (1 -> 0, 2 -> -2, 3 -> -4, 4 -> -6, 5+ -> -8)."""
        return self.revisitPenaltyFor(max(0, int(visitNumber) - 1))

    def boneScoreReductionFor(self, boneNumber, completedAllFive=False):
        """Return training score reduction for collecting the `boneNumber`-th Bone (1..5).
        Bones 1..4 each provide -10; the 5th Bone provides -20 (total -60 when all 5 are collected).
        """
        if int(boneNumber) >= MAX_BONES or bool(completedAllFive):
            return float(self.fifthBoneScoreReduction)
        return float(self.boneScoreReduction)

    def boneRewardFor(self, boneNumber, completedAllFive=False):
        """Return positive RL reward for collecting the `boneNumber`-th Bone (1..5).
        The 5th Bone gives double the reward of an ordinary Bone (+20 vs +10, total +60).
        """
        if int(boneNumber) >= MAX_BONES or bool(completedAllFive):
            return float(self.fifthBoneReward)
        return float(self.boneReward)

    def toDict(self):
        return {key: getattr(self, key) for key in self.FIELDS}


class MazeEnvironment:
    def __init__(
        self,
        mazeData,
        maxSteps=300,
        rewardConfig=None,
        normalizeObservation=True,
        enforceScoreLimit=True,
        priorMazeMemory=None,
    ):
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
        if len(self.bones) > MAX_BONES:
            raise ValueError(f"Maze cannot have more than 5 bones, found {len(self.bones)}")

        validation = validateMaze(mazeData, requireWallSync=True)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))

        self.orderedBones = sorted(self.bones, key=lambda pos: (pos[1], pos[0]))
        self.maxSteps = int(maxSteps)
        self.rewardConfig = RewardConfig.coerce(rewardConfig)
        self.enforceScoreLimit = bool(enforceScoreLimit)
        self.encoder = ObservationEncoder(normalize=normalizeObservation)
        self.observationSize = OBSERVATION_SIZE
        self._neighborCache = {}
        self.priorMazeMemory = self._initPriorMazeMemory(priorMazeMemory)
        self.steps = 0
        self.visitCounts = {}
        self.reset()

    def _initPriorMazeMemory(self, initial=None):
        base = {
            "attemptsCompleted": 0,
            "cumulativeVisitedCells": set(),
            "cumulativeDiscoveredCells": set(),
            "cumulativeDeadEnds": set(),
            "cumulativeDeadEndEdges": set(),
            "cumulativeJunctions": set(),
            "cumulativeDiscoveredPits": set(),
            "cumulativeTraversedEdges": set(),
            "historicalLoopEdges": set(),
            "bestTrainingScore": None,
            "bestOfficialScore": None,
            "bestTrajectory": [],
        }
        if isinstance(initial, dict):
            base["attemptsCompleted"] = int(initial.get("attemptsCompleted", 0))
            for setKey in (
                "cumulativeVisitedCells",
                "cumulativeDiscoveredCells",
                "cumulativeDeadEnds",
                "cumulativeDeadEndEdges",
                "cumulativeJunctions",
                "cumulativeDiscoveredPits",
                "cumulativeTraversedEdges",
                "historicalLoopEdges",
            ):
                rawItems = initial.get(setKey, ())
                base[setKey] = {tuple(x) if isinstance(x, (list, tuple)) else x for x in rawItems}
            base["bestTrainingScore"] = initial.get("bestTrainingScore")
            base["bestOfficialScore"] = initial.get("bestOfficialScore")
            base["bestTrajectory"] = list(initial.get("bestTrajectory") or [])
        return base

    def _archiveEpisodeIntoPriorMemory(self):
        if getattr(self, "steps", 0) <= 0 or not getattr(self, "visitCounts", None):
            return
        pm = self.priorMazeMemory
        pm["attemptsCompleted"] += 1
        pm["cumulativeVisitedCells"].update(self.visitCounts.keys())
        pm["cumulativeDiscoveredCells"].update(getattr(self, "discoveredCells", ()))
        pm["cumulativeDeadEnds"].update(getattr(self, "knownDeadEnds", ()))
        pm["cumulativeDeadEndEdges"].update(getattr(self, "deadEndEdges", ()))
        pm["cumulativeJunctions"].update(getattr(self, "knownJunctions", ()))
        pm["cumulativeDiscoveredPits"].update(getattr(self, "discoveredPits", ()))
        for (pos, act) in getattr(self, "edgeCounts", {}).keys():
            pm["cumulativeTraversedEdges"].add((int(pos[0]), int(pos[1]), int(act)))
        pm["historicalLoopEdges"].update(getattr(self, "loopEdges", ()))
        won = bool(self.position in self.ends and not self.scoreLimitExceeded)
        if won:
            if pm["bestTrainingScore"] is None or self.trainingScore < pm["bestTrainingScore"]:
                pm["bestTrainingScore"] = int(self.trainingScore)
                pm["bestOfficialScore"] = int(self.currentScore())
                pm["bestTrajectory"] = list(self.actionHistory)

    def inside(self, position):
        return 0 <= position[0] < self.width and 0 <= position[1] < self.height

    def reset(self):
        self._archiveEpisodeIntoPriorMemory()
        self.position = self.starts[0]
        self.remainingBones = set(self.bones)
        self.collectedBones = set()
        self.collectedBonesOrder = []
        self.boneCollectionEvents = []
        self.steps = 0
        self.movedSteps = 0
        self.totalBoneScoreReduction = 0
        self.trainingScore = 0
        self.done = False
        self.scoreLimitExceeded = False
        self.failed = False
        self.visitCounts = {self.position: 1}
        self.pitVisitCounts = {}
        self.edgeCounts = {}
        self.exploredDirections = {self.position: set()}
        self.discoveredCells = {self.position}
        self.discoveredWalls = set()
        self.discoveredConnections = set()
        self.discoveredPits = set()
        self.knownDeadEnds = set()
        self.knownJunctions = set()
        self.deadEndEdges = set()
        self.loopPaths = []
        self.loopEdges = set()
        self.revisits = 0
        self.wallBumps = 0
        self.deadEndsEncountered = 0
        self.deadEndReentries = 0
        self.repeatedSequencesCount = 0
        self.repeatedCorridorEntries = 0
        self.noProgressStreak = 0
        self.unsuccessfulObjectiveAttempts = 0
        self.avoidedPreviousMistakes = 0
        self.lastStepWasMistake = False
        self.lastStepAvoidedMistake = False
        self.lastStepFoundDeadEnd = False
        self.actionHistory = []
        self.positionHistory = [list(self.position)]
        self.lastAction = None
        self.lastMoved = True
        self.lastTeleported = False
        self.lastBoneCollected = False
        self.lastPitEntered = None
        self.lastObjectiveProgress = 0.0
        self.currentTarget = None
        self.currentTargetType = "bone"
        self.minDistToCurrentTarget = None
        self.cumulativeReward = 0.0
        self.rawCumulativeReward = 0.0
        self._recordLocalDiscovery(self.position)
        self._updateDiscoveredTopology()
        self._updateActiveTarget(initial=True)
        return self.observe()

    def _manhattan(self, a, b):
        return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))

    def _nearestEnd(self, fromPos=None):
        px, py = self.position if fromPos is None else fromPos
        return min(self.ends, key=lambda pos: (abs(pos[0] - px) + abs(pos[1] - py), pos[1], pos[0]))

    def _updateActiveTarget(self, initial=False):
        """Maintain a stable target objective with hysteresis so the Dog does not
        repeatedly switch between targets without a reason."""
        pos = self.position
        if not self.remainingBones:
            self.currentTarget = self._nearestEnd(pos)
            self.currentTargetType = "end"
            self.minDistToCurrentTarget = self._manhattan(pos, self.currentTarget)
            return

        nearestBone = min(
            self.remainingBones,
            key=lambda b: (self._manhattan(pos, b), b[1], b[0]),
        )
        nearestDist = self._manhattan(pos, nearestBone)

        if (
            initial
            or self.currentTarget is None
            or self.currentTargetType != "bone"
            or self.currentTarget not in self.remainingBones
        ):
            self.currentTarget = nearestBone
            self.currentTargetType = "bone"
            self.minDistToCurrentTarget = nearestDist
            return

        currentDist = self._manhattan(pos, self.currentTarget)
        # Switch to a different uncollected Bone only if it is substantially closer
        # (hysteresis margin >= 2 steps) or we hit a dead end pursuing the old one.
        if nearestBone != self.currentTarget and (
            nearestDist + 2 < currentDist or self.lastStepFoundDeadEnd
        ):
            self.currentTarget = nearestBone
            self.currentTargetType = "bone"
            self.minDistToCurrentTarget = nearestDist
        else:
            if self.minDistToCurrentTarget is None or currentDist < self.minDistToCurrentTarget:
                self.minDistToCurrentTarget = currentDist

    def _recordLocalDiscovery(self, pos):
        """Update discovered cells, walls, connections, and adjacent pits from `pos`."""
        self.discoveredCells.add(pos)
        if pos in self.pits:
            self.discoveredPits.add(pos)
        for action in range(4):
            nb = self.neighborAt(pos, action)
            if nb is not None:
                self.discoveredCells.add(nb)
                self.discoveredConnections.add((pos, action, nb))
                if nb in self.pits:
                    self.discoveredPits.add(nb)
            else:
                self.discoveredWalls.add((pos, action))

    def _updateDiscoveredTopology(self):
        """Identify known junctions and dead ends using ONLY visited cells and their
        observed open doorways. Never inspects unvisited corridors or the hidden maze."""
        for v in self.visitCounts:
            openNeighbors = [self.neighborAt(v, a) for a in range(4) if self.neighborAt(v, a) is not None]
            if len(openNeighbors) >= 3:
                self.knownJunctions.add(v)

        # Iterative pruning on visited cells:
        # A visited cell v (not an End, not holding an uncollected Bone) is a dead end if:
        #   - v != start and at most 1 of its open neighbors is not already in knownDeadEnds
        #   - OR v == start and len(openNeighbors) == 1 and self.position != start (so start itself
        #     is a degree-1 cap, without propagating dead-end status forward out of start).
        deadEnds = set()
        startPos = self.starts[0]
        changed = True
        while changed:
            changed = False
            for v in self.visitCounts:
                if v in deadEnds or v in self.ends or v in self.remainingBones:
                    continue
                if v == startPos:
                    continue
                openNeighbors = [self.neighborAt(v, a) for a in range(4) if self.neighborAt(v, a) is not None]
                if v in self.pits and self.pits[v] in self.visitCounts:
                    openNeighbors.append(self.pits[v])
                activeExits = [nb for nb in openNeighbors if nb not in deadEnds]
                if len(activeExits) <= 1:
                    deadEnds.add(v)
                    changed = True

        # If Start itself has only 1 open doorway and the Dog has already stepped out of Start,
        # mark Start as a dead-end destination so the Dog does not pointlessly re-enter Start.
        if (
            startPos not in self.ends
            and startPos not in self.remainingBones
            and self.position != startPos
        ):
            startOpen = [self.neighborAt(startPos, a) for a in range(4) if self.neighborAt(startPos, a) is not None]
            if len(startOpen) <= 1:
                deadEnds.add(startPos)

        self.knownDeadEnds = deadEnds
        for (pos, act) in self.edgeCounts:
            nb = self.neighborAt(pos, act)
            if nb is not None and nb in self.knownDeadEnds and nb not in self.remainingBones and nb not in self.ends:
                self.deadEndEdges.add((int(pos[0]), int(pos[1]), int(act)))

    @property
    def visited(self):
        return set(self.visitCounts)

    def visitCountAt(self, position):
        return self.visitCounts.get(position, 0) + self.pitVisitCounts.get(position, 0)

    def maxVisitCount(self):
        return max(self.visitCounts.values()) if self.visitCounts else 0

    def mostVisitedCell(self):
        if not self.visitCounts:
            return None
        pos, _ = max(self.visitCounts.items(), key=lambda kv: (kv[1], -kv[0][1], -kv[0][0]))
        return [int(pos[0]), int(pos[1])]

    def mostFrequentlyRevisitedCell(self):
        revisited = [(pos, cnt) for pos, cnt in self.visitCounts.items() if cnt > 1]
        if not revisited:
            return None
        pos, _ = max(revisited, key=lambda kv: (kv[1], -kv[0][1], -kv[0][0]))
        return [int(pos[0]), int(pos[1])]

    def revisitPercentage(self):
        if self.steps <= 0:
            return 0.0
        return 100.0 * float(self.revisits) / float(self.steps)

    def newAreasExploredCount(self):
        priorVisited = self.priorMazeMemory.get("cumulativeVisitedCells", set())
        if not priorVisited:
            return len(self.visitCounts)
        return len(set(self.visitCounts.keys()) - set(priorVisited))

    def totalMistakesCount(self):
        return int(
            self.deadEndReentries
            + self.repeatedSequencesCount
            + self.repeatedCorridorEntries
            + self.wallBumps
        )

    def localView(self, normalize=False):
        return self.encoder.encodeLocalView(self, normalize=normalize)

    def actionMask(self):
        return self.encoder.encodeActionMask(self)

    def navigationInfo(self):
        nav = self.encoder.encodeNavigation(self)
        return {
            "isDeadEnd": nav["isDeadEnd"],
            "isCorridor": nav["isCorridor"],
            "isJunction": nav["isJunction"],
            "hasMultipleExits": nav["hasMultipleExits"],
            "openExitsCount": nav["openExitsCount"],
            "nonDeadEndExitsCount": nav["nonDeadEndExitsCount"],
            "availableActions": self.availableActions(),
            "actionMask": [float(x) for x in self.actionMask()],
            "exploredExits": [bool(x > 0.5) for x in nav["exploredExits"]],
            "unexploredExits": [bool(x > 0.5) for x in nav["unexploredExits"]],
            "deadEndExits": [bool(x > 0.5) for x in nav["deadEndExits"]],
            "knownDeadEnds": [[int(p[0]), int(p[1])] for p in sorted(self.knownDeadEnds)],
            "knownJunctions": [[int(p[0]), int(p[1])] for p in sorted(self.knownJunctions)],
        }

    def explorationMemory(self):
        """Return exploration memory split into policy-visible episodic memory and
        training-only cross-attempt diagnostics."""
        pm = self.priorMazeMemory
        return {
            "episodic": {
                "visitedCells": [[int(p[0]), int(p[1])] for p in sorted(self.visitCounts.keys())],
                "discoveredCells": [[int(p[0]), int(p[1])] for p in sorted(self.discoveredCells)],
                "traversedConnections": [
                    {"from": [int(p[0]), int(p[1])], "action": int(a), "count": int(c)}
                    for (p, a), c in sorted(self.edgeCounts.items())
                ],
                "exploredDirections": {
                    f"{p[0]},{p[1]}": sorted(int(a) for a in acts)
                    for p, acts in sorted(self.exploredDirections.items())
                    if acts
                },
                "knownDeadEnds": [[int(p[0]), int(p[1])] for p in sorted(self.knownDeadEnds)],
                "knownJunctions": [[int(p[0]), int(p[1])] for p in sorted(self.knownJunctions)],
                "discoveredPits": [[int(p[0]), int(p[1])] for p in sorted(self.discoveredPits)],
                "collectedBones": [[int(p[0]), int(p[1])] for p in self.collectedBonesOrder],
                "loopPaths": list(self.loopPaths),
                "newAreasExplored": self.newAreasExploredCount(),
            },
            "trainingDiagnostics": {
                "attemptsCompleted": int(pm["attemptsCompleted"]),
                "cumulativeVisitedCellsCount": len(pm["cumulativeVisitedCells"]),
                "cumulativeDiscoveredCellsCount": len(pm["cumulativeDiscoveredCells"]),
                "cumulativeDeadEnds": [[int(p[0]), int(p[1])] for p in sorted(pm["cumulativeDeadEnds"])],
                "cumulativeDeadEndEdges": [list(e) for e in sorted(pm["cumulativeDeadEndEdges"])],
                "cumulativeJunctions": [[int(p[0]), int(p[1])] for p in sorted(pm["cumulativeJunctions"])],
                "cumulativeDiscoveredPits": [[int(p[0]), int(p[1])] for p in sorted(pm["cumulativeDiscoveredPits"])],
                "cumulativeTraversedEdgesCount": len(pm["cumulativeTraversedEdges"]),
                "historicalLoopEdges": [list(e) for e in sorted(pm["historicalLoopEdges"])],
                "bestTrainingScore": pm["bestTrainingScore"],
                "bestOfficialScore": pm["bestOfficialScore"],
            },
        }

    def objectiveInfo(self):
        obj = self.encoder.encodeObjectives(self)
        return {
            "bones": self.boneObservations(),
            "nearestEnd": obj["nearestEnd"],
            "endDx": obj["endDx"],
            "endDy": obj["endDy"],
            "endDxNorm": obj["endDxNorm"],
            "endDyNorm": obj["endDyNorm"],
            "endDistNorm": obj["endDistNorm"],
            "activeObjective": obj["activeObjective"],
            "objectiveProgress": obj["objectiveProgress"],
            "madeProgress": obj["madeProgress"],
        }

    def mistakeInfo(self):
        return {
            "deadEndsEncountered": int(self.deadEndsEncountered),
            "deadEndReentries": int(self.deadEndReentries),
            "repeatedSequences": int(self.repeatedSequencesCount),
            "repeatedCorridorEntries": int(self.repeatedCorridorEntries),
            "wallBumps": int(self.wallBumps),
            "noProgressStreak": int(self.noProgressStreak),
            "unsuccessfulObjectiveAttempts": int(self.unsuccessfulObjectiveAttempts),
            "totalMistakes": self.totalMistakesCount(),
            "avoidedPreviousMistakes": int(self.avoidedPreviousMistakes),
        }

    def boneLocations(self):
        return [[int(bx), int(by)] for bx, by in self.orderedBones]

    def boneObservations(self):
        return self.encoder.encodeBones(self)

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
        """Official multiplayer score: Steps - 5 * Bones Collected."""
        return self.steps - 5 * self.bonesCollected()

    def currentTrainingScore(self):
        """Training score: Steps + totalBoneScoreReduction (-10 per Bone 1..4, -20 for 5th Bone)."""
        return int(self.trainingScore)

    def step(self, action):
        if self.done:
            raise RuntimeError("Episode already finished")
        actionIndex = self.parseAction(action)
        previousPosition = self.position
        priorKnownDeadEnds = set(self.knownDeadEnds)
        priorDeadEndEdges = self.priorMazeMemory.get("cumulativeDeadEndEdges", set()) | self.deadEndEdges
        priorLoopEdges = self.priorMazeMemory.get("historicalLoopEdges", set()) | self.loopEdges

        activeTargetBefore = self.currentTarget if (self.currentTarget is not None) else self._nearestEnd(previousPosition)
        distBefore = self._manhattan(previousPosition, activeTargetBefore)

        edgeKey = (previousPosition, actionIndex)
        priorEdgeCount = self.edgeCounts.get(edgeKey, 0)
        self.edgeCounts[edgeKey] = priorEdgeCount + 1
        self.exploredDirections.setdefault(previousPosition, set()).add(actionIndex)

        target = self.neighbor(actionIndex)
        moved = target is not None
        if moved:
            self.position = target
            self.movedSteps += 1
        teleported = False
        pitEntered = None
        if moved and self.position in self.pits:
            pitEntered = list(self.position)
            self.discoveredPits.add(self.position)
            seenPits = set()
            while self.position in self.pits and self.position not in seenPits:
                seenPits.add(self.position)
                self.discoveredPits.add(self.position)
                self.pitVisitCounts[self.position] = self.pitVisitCounts.get(self.position, 0) + 1
                self.position = self.pits[self.position]
                teleported = True

        # Check if the Dog avoided a known dead-end or loop edge at `previousPosition`
        avoidedMistake = False
        if moved:
            openFromPrev = [a for a in range(4) if self.neighborAt(previousPosition, a) is not None]
            if len(openFromPrev) >= 2:
                badChoices = {
                    a
                    for a in openFromPrev
                    if (int(previousPosition[0]), int(previousPosition[1]), int(a)) in priorDeadEndEdges
                    or (int(previousPosition[0]), int(previousPosition[1]), int(a)) in priorLoopEdges
                    or (self.neighborAt(previousPosition, a) in priorKnownDeadEnds)
                }
                if badChoices and actionIndex not in badChoices and self.position not in priorKnownDeadEnds:
                    avoidedMistake = True
                    self.avoidedPreviousMistakes += 1
        self.lastStepAvoidedMistake = avoidedMistake

        rc = self.rewardConfig
        bone = self.position in self.remainingBones
        stepBoneScoreReduction = 0
        stepBoneReward = 0.0
        completedAllFive = False
        if bone:
            self.remainingBones.remove(self.position)
            self.collectedBones.add(self.position)
            self.collectedBonesOrder.append(self.position)
            boneNumber = len(self.collectedBonesOrder)
            completedAllFive = (boneNumber == MAX_BONES and len(self.remainingBones) == 0)
            stepBoneScoreReduction = int(round(rc.boneScoreReductionFor(boneNumber, completedAllFive=completedAllFive)))
            stepBoneReward = float(rc.boneRewardFor(boneNumber, completedAllFive=completedAllFive))
            self.totalBoneScoreReduction += stepBoneScoreReduction
            self.boneCollectionEvents.append({
                "boneNumber": boneNumber,
                "position": [int(self.position[0]), int(self.position[1])],
                "step": self.steps + 1,
                "scoreReduction": stepBoneScoreReduction,
                "reward": stepBoneReward,
                "completedAllFive": bool(completedAllFive),
            })

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
        visitNumber = self.visitCounts.get(self.position, 1)

        self.steps += 1
        self.actionHistory.append(actionIndex)
        self.positionHistory.append([int(self.position[0]), int(self.position[1])])
        self.lastAction = actionIndex
        self.lastMoved = moved
        self.lastTeleported = teleported
        self.lastBoneCollected = bone
        self.lastPitEntered = pitEntered

        self._recordLocalDiscovery(self.position)
        self._updateDiscoveredTopology()

        # Detect dead-end discovery vs dead-end re-entry
        openHere = self.availableActionIndices()
        enteredKnownDeadEnd = bool(
            moved
            and not bone
            and (self.position not in self.ends)
            and (
                self.position in priorKnownDeadEnds
                or (int(previousPosition[0]), int(previousPosition[1]), int(actionIndex)) in self.priorMazeMemory.get("cumulativeDeadEndEdges", set())
            )
        )
        newlyFoundDeadEnd = bool(
            moved
            and (self.position in self.knownDeadEnds or len(openHere) <= 1)
            and (self.position not in priorKnownDeadEnds)
            and (self.position not in self.ends)
        )
        if newlyFoundDeadEnd or enteredKnownDeadEnd:
            self.deadEndsEncountered += 1
        if enteredKnownDeadEnd:
            self.deadEndReentries += 1
        self.lastStepFoundDeadEnd = newlyFoundDeadEnd

        # Detect repeated movement sequences (oscillation A -> B -> A -> B) and corridor loops
        repeatedSequence = False
        if (
            moved
            and not bone
            and not newCell
            and len(self.positionHistory) >= 4
            and self.positionHistory[-1] == self.positionHistory[-3]
            and self.positionHistory[-2] == self.positionHistory[-4]
            and len(openFromPrev) >= 2
        ):
            repeatedSequence = True
            self.repeatedSequencesCount += 1
            self.loopEdges.add((int(previousPosition[0]), int(previousPosition[1]), int(actionIndex)))
            self.loopPaths.append({
                "step": self.steps,
                "from": list(previousPosition),
                "to": list(self.position),
                "type": "oscillation",
            })

        repeatedCorridor = False
        if moved and not bone and priorEdgeCount >= 2:
            repeatedCorridor = True
            self.repeatedCorridorEntries += 1
            self.loopEdges.add((int(previousPosition[0]), int(previousPosition[1]), int(actionIndex)))
            if len(self.loopPaths) < 50:
                self.loopPaths.append({
                    "step": self.steps,
                    "from": list(previousPosition),
                    "to": list(self.position),
                    "type": "repeated_corridor",
                })

        # Objective progress calculation
        reachedEnd = self.position in self.ends
        distAfter = self._manhattan(self.position, activeTargetBefore)
        if bone or reachedEnd:
            self.lastObjectiveProgress = 1.0
            self.noProgressStreak = 0
        elif not moved:
            self.lastObjectiveProgress = -1.0
            self.noProgressStreak += 1
        elif distAfter < distBefore:
            self.lastObjectiveProgress = 1.0
            self.noProgressStreak = 0
        elif distAfter > distBefore:
            self.lastObjectiveProgress = -1.0
            if not newCell:
                self.noProgressStreak += 1
                if self.minDistToCurrentTarget is not None and distBefore <= 2 and distAfter >= self.minDistToCurrentTarget + 2:
                    self.unsuccessfulObjectiveAttempts += 1
            else:
                self.noProgressStreak = 0
        else:
            self.lastObjectiveProgress = 0.0
            if not newCell:
                self.noProgressStreak += 1

        self.lastStepWasMistake = bool(enteredKnownDeadEnd or repeatedSequence or repeatedCorridor or (not moved))
        self._updateActiveTarget(initial=False)

        self.trainingScore = int(round(self.steps * rc.stepScoreCost + self.totalBoneScoreReduction))
        officialScore = self.steps - 5 * self.bonesCollected()

        scoreLimitExceeded = bool(self.enforceScoreLimit and (self.trainingScore > rc.maxScoreLimit))
        won = bool(reachedEnd and not scoreLimitExceeded)
        timeout = bool((not won) and (not scoreLimitExceeded) and (self.steps >= self.maxSteps))
        failed = bool((not won) and (scoreLimitExceeded or timeout))

        self.scoreLimitExceeded = scoreLimitExceeded
        self.failed = failed
        self.done = won or scoreLimitExceeded or timeout

        breakdown = {"move": rc.movePenalty}
        if not moved:
            breakdown["wall"] = rc.wallPenalty
        if newCell:
            breakdown["novelty"] = rc.noveltyReward
        if revisit:
            breakdown["revisit"] = rc.revisitPenaltyFor(priorVisits)
            if enteredKnownDeadEnd and getattr(rc, "deadEndPenalty", 0.0) != 0.0:
                breakdown["deadEnd"] = float(rc.deadEndPenalty)
            if (repeatedSequence or repeatedCorridor) and getattr(rc, "loopPenalty", 0.0) != 0.0:
                breakdown["mistake"] = float(rc.loopPenalty)
        if bone:
            breakdown["bone"] = float(rc.boneReward)
            if completedAllFive:
                extraFifth = float(stepBoneReward - rc.boneReward)
                if extraFifth != 0.0:
                    breakdown["allBones"] = extraFifth
        if won:
            breakdown["end"] = rc.endReward
        elif scoreLimitExceeded:
            breakdown["scoreLimit"] = rc.scoreLimitPenalty
            breakdown["failure"] = rc.failurePenalty
        elif timeout:
            breakdown["stepLimit"] = rc.stepLimitPenalty
            breakdown["failure"] = rc.failurePenalty
        reward = float(sum(breakdown.values()))

        # Official-score-aligned signal (negated official score delta) kept for reporting only.
        rawReward = -1.0 + (5.0 if bone else 0.0)
        self.rawCumulativeReward += rawReward
        self.cumulativeReward += reward

        bonesCollected = self.bonesCollected()
        revisitPenaltyApplied = float(breakdown.get("revisit", 0.0))
        navInfo = self.navigationInfo()
        info = {
            "action": actionIndex,
            "actionName": ACTION_NAMES[actionIndex],
            "previousPosition": list(previousPosition),
            "position": list(self.position),
            "pitEntered": pitEntered,
            "moved": moved,
            "teleported": teleported,
            "bone": bone,
            "completedAllFiveBones": completedAllFive,
            "boneScoreReduction": stepBoneScoreReduction,
            "totalBoneScoreReduction": self.totalBoneScoreReduction,
            "boneReward": stepBoneReward,
            "won": won,
            "timeout": timeout,
            "scoreLimitExceeded": scoreLimitExceeded,
            "failed": failed,
            "steps": self.steps,
            "bonesCollected": bonesCollected,
            "totalBones": len(self.bones),
            "remainingBonesCount": len(self.remainingBones),
            "score": officialScore,
            "officialScore": officialScore,
            "trainingScore": self.trainingScore,
            "maxScoreLimit": int(rc.maxScoreLimit),
            "done": self.done,
            "newCell": newCell,
            "revisit": revisit,
            "visitCount": visitNumber,
            "revisitPenalty": revisitPenaltyApplied,
            "wallBump": not moved,
            "revisits": self.revisits,
            "wallBumps": self.wallBumps,
            "uniqueCells": len(self.visitCounts),
            "discoveredCellsCount": len(self.discoveredCells),
            "newAreasExplored": self.newAreasExploredCount(),
            "maxVisitCount": self.maxVisitCount(),
            "mostVisitedCell": self.mostVisitedCell(),
            "mostFrequentlyRevisitedCell": self.mostFrequentlyRevisitedCell(),
            "revisitPercentage": self.revisitPercentage(),
            "revisitRate": float(self.revisits) / float(max(1, self.steps)),
            "visitedCells": [[int(p[0]), int(p[1])] for p in self.visitCounts.keys()],
            "collectedBones": [[int(p[0]), int(p[1])] for p in self.collectedBonesOrder],
            "boneCollectionEvents": list(self.boneCollectionEvents),
            "isDeadEnd": navInfo["isDeadEnd"],
            "isCorridor": navInfo["isCorridor"],
            "isJunction": navInfo["isJunction"],
            "deadEndsEncountered": self.deadEndsEncountered,
            "deadEndReentries": self.deadEndReentries,
            "repeatedMistakes": self.totalMistakesCount(),
            "avoidedPreviousMistakes": self.avoidedPreviousMistakes,
            "objectiveProgress": self.lastObjectiveProgress,
            "reward": reward,
            "rewardBreakdown": breakdown,
            "rawReward": rawReward,
            "cumulativeReward": self.cumulativeReward,
            "rawCumulativeReward": self.rawCumulativeReward,
            "availableActions": self.availableActions(),
            "actionMask": [float(x) for x in self.actionMask()],
        }
        return self.observe(), reward, self.done, info

    def state(self):
        bonesCollected = self.bonesCollected()
        officialScore = self.steps - 5 * bonesCollected
        navInfo = self.navigationInfo()
        return {
            "position": list(self.position),
            "steps": self.steps,
            "done": self.done,
            "won": bool(self.position in self.ends and not self.scoreLimitExceeded),
            "timeout": bool((self.position not in self.ends) and not self.scoreLimitExceeded and (self.steps >= self.maxSteps)),
            "scoreLimitExceeded": self.scoreLimitExceeded,
            "failed": self.failed,
            "bonesCollected": bonesCollected,
            "remainingBones": [list(x) for x in sorted(self.remainingBones)],
            "collectedBones": [[int(p[0]), int(p[1])] for p in self.collectedBonesOrder],
            "boneLocations": self.boneLocations(),
            "boneObservations": self.boneObservations(),
            "score": officialScore,
            "officialScore": officialScore,
            "trainingScore": self.trainingScore,
            "totalBoneScoreReduction": self.totalBoneScoreReduction,
            "maxScoreLimit": int(self.rewardConfig.maxScoreLimit),
            "revisits": self.revisits,
            "uniqueCells": len(self.visitCounts),
            "discoveredCellsCount": len(self.discoveredCells),
            "newAreasExplored": self.newAreasExploredCount(),
            "maxVisitCount": self.maxVisitCount(),
            "mostVisitedCell": self.mostVisitedCell(),
            "mostFrequentlyRevisitedCell": self.mostFrequentlyRevisitedCell(),
            "revisitPercentage": round(self.revisitPercentage(), 2),
            "deadEndsEncountered": self.deadEndsEncountered,
            "deadEndReentries": self.deadEndReentries,
            "repeatedMistakes": self.totalMistakesCount(),
            "avoidedPreviousMistakes": self.avoidedPreviousMistakes,
            "navigation": navInfo,
            "objectives": self.objectiveInfo(),
            "cumulativeReward": round(self.cumulativeReward, 4),
            "availableActions": self.availableActions(),
            "actionMask": [float(x) for x in self.actionMask()],
            "localView": self.localView(normalize=False).tolist(),
            "observation": [round(float(x), 4) for x in self.observe()],
            "grid": self.grid,
        }
