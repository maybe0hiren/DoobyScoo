"""DoobyScoo MazeEnvironment with rebuilt reward system, oscillation detection,
revisit penalties, dead-end pruning, score-aware target locking, and active
episodic navigation guidance under strict partial observability.
"""
from collections import deque
import json
from pathlib import Path
import numpy as np
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
    """Rebuilt RL reward & training score specification.

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
        - 1st visit (priorVisits == 0): 0.0 (only normal movePenalty -1.0 applies)
        - 2nd visit (priorVisits == 1): revisitPenalty (-2.5)
        - 3rd visit (priorVisits == 2): revisitPenalty + repeatedRevisitPenalty (-5.0)
        - 4th visit (priorVisits == 3): revisitPenalty + 2 * repeatedRevisitPenalty (-7.5)
        - 5th+ visit (priorVisits >= 4): capped at maxRevisitPenalty (-10.0)
        """
        if priorVisits <= 0:
            return float(self.firstVisitPenalty)
        penalty = float(self.revisitPenalty) + float(self.repeatedRevisitPenalty) * (int(priorVisits) - 1)
        return max(float(self.maxRevisitPenalty), penalty)

    def revisitPenaltyForVisit(self, visitNumber):
        """Return training penalty by 1-based visit number."""
        return self.revisitPenaltyFor(max(0, int(visitNumber) - 1))

    def boneScoreReductionFor(self, boneNumber, completedAllFive=False):
        """Return training score reduction for collecting the `boneNumber`-th Bone (1..5)."""
        if int(boneNumber) >= MAX_BONES or bool(completedAllFive):
            return float(self.fifthBoneScoreReduction)
        return float(self.boneScoreReduction)

    def boneRewardFor(self, boneNumber, completedAllFive=False):
        """Return positive RL reward for collecting the `boneNumber`-th Bone (1..5)."""
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
        self.navConfig = dict(DEFAULT_CONFIG["navigation"])
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
        self.lastVisitedStep = {self.position: 0}
        self.pitVisitCounts = {}
        self.discoveredPitTargets = {}
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
        self.suppressedTargets = set()
        self.revisits = 0
        self.wallBumps = 0
        self.deadEndsEncountered = 0
        self.deadEndReentries = 0
        self.repeatedSequencesCount = 0
        self.repeatedCorridorEntries = 0
        self.oscillationsDetected = 0
        self.immediateReversalsCount = 0
        self.oscillationActive = False
        self.noProgressStreak = 0
        self.targetStallSteps = 0
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

    def _selectWorthwhileBone(self, pos):
        """Score-aware Bone evaluation under partial observability.

        Collecting a Bone reduces the official score by 5 points.
        Therefore, a Bone is worth pursuing when the estimated extra detour cost
            detour(B) = dist(pos, B) + dist(B, End) - dist(pos, End)
        is at most `maxDetourStepsPerBone` (default 7 steps), OR when the Bone
        is immediately nearby (Manhattan distance <= 4).
        Bones that have stalled progress repeatedly (`suppressedTargets`) or
        lie inside known dead ends without direct access are deprioritized.
        """
        if not self.remainingBones:
            return None
        nearestEnd = self._nearestEnd(pos)
        distToEnd = self._manhattan(pos, nearestEnd)
        maxDetour = int(self.navConfig.get("maxDetourStepsPerBone", 7))

        candidates = []
        for bonePos in self.remainingBones:
            if bonePos in self.suppressedTargets:
                continue
            dBone = self._manhattan(pos, bonePos)
            dBoneToEnd = self._manhattan(bonePos, nearestEnd)
            detour = (dBone + dBoneToEnd) - distToEnd
            if dBone <= 4 or detour <= maxDetour:
                # Net score utility: lower effective cost is better
                effectiveCost = dBone + 0.65 * max(0, detour)
                candidates.append((effectiveCost, dBone, bonePos[1], bonePos[0], bonePos))

        if candidates:
            candidates.sort()
            return candidates[0][-1]

        # If all remaining Bones require huge detours, check if any unsuppressed Bone is very close
        unsuppressed = [b for b in self.remainingBones if b not in self.suppressedTargets]
        if unsuppressed:
            closest = min(unsuppressed, key=lambda b: (self._manhattan(pos, b), b[1], b[0]))
            if self._manhattan(pos, closest) <= 3:
                return closest
        return None

    def _updateActiveTarget(self, initial=False):
        """Maintain a persistent score-aware objective with hysteresis and stall recovery."""
        pos = self.position
        nearestEnd = self._nearestEnd(pos)

        if not self.remainingBones:
            self.currentTarget = nearestEnd
            self.currentTargetType = "end"
            self.minDistToCurrentTarget = self._manhattan(pos, nearestEnd)
            self.targetStallSteps = 0
            return

        # If currently locked onto a Bone that has stalled for too many steps, suppress it
        maxStall = int(self.navConfig.get("maxStallStepsOnTarget", 6))
        if (
            not initial
            and self.currentTarget is not None
            and self.currentTargetType == "bone"
            and self.targetStallSteps >= maxStall
        ):
            self.suppressedTargets.add(self.currentTarget)
            self.unsuccessfulObjectiveAttempts += 1
            self.currentTarget = None
            self.targetStallSteps = 0

        bestBone = self._selectWorthwhileBone(pos)
        if bestBone is None:
            self.currentTarget = nearestEnd
            self.currentTargetType = "end"
            self.minDistToCurrentTarget = self._manhattan(pos, nearestEnd)
            return

        bestDist = self._manhattan(pos, bestBone)
        if (
            initial
            or self.currentTarget is None
            or self.currentTargetType != "bone"
            or self.currentTarget not in self.remainingBones
            or self.currentTarget in self.suppressedTargets
        ):
            self.currentTarget = bestBone
            self.currentTargetType = "bone"
            self.minDistToCurrentTarget = bestDist
            self.targetStallSteps = 0
            return

        currentDist = self._manhattan(pos, self.currentTarget)
        hysteresis = int(self.navConfig.get("hysteresisMargin", 2))
        if bestBone != self.currentTarget and (
            bestDist + hysteresis < currentDist or self.lastStepFoundDeadEnd
        ):
            self.currentTarget = bestBone
            self.currentTargetType = "bone"
            self.minDistToCurrentTarget = bestDist
            self.targetStallSteps = 0
        else:
            if self.minDistToCurrentTarget is None or currentDist < self.minDistToCurrentTarget:
                self.minDistToCurrentTarget = currentDist
                self.targetStallSteps = 0

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
        observed open doorways. Never inspects unvisited corridors or hidden maze structure."""
        for v in self.visitCounts:
            openNeighbors = [self.neighborAt(v, a) for a in range(4) if self.neighborAt(v, a) is not None]
            if len(openNeighbors) >= 3:
                self.knownJunctions.add(v)

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
                if v in self.discoveredPitTargets and self.discoveredPitTargets[v] in self.visitCounts:
                    openNeighbors.append(self.discoveredPitTargets[v])
                activeExits = [nb for nb in openNeighbors if nb not in deadEnds]
                if len(activeExits) <= 1:
                    deadEnds.add(v)
                    changed = True

        if (
            startPos not in self.ends
            and startPos not in self.remainingBones
            and self.position != startPos
        ):
            startOpen = [self.neighborAt(startPos, a) for a in range(4) if self.neighborAt(startPos, a) is not None]
            activeStartExits = [nb for nb in startOpen if nb not in deadEnds]
            if len(activeStartExits) <= 1:
                deadEnds.add(startPos)

        self.knownDeadEnds = deadEnds
        for (pos, act) in self.edgeCounts:
            nb = self.neighborAt(pos, act)
            if nb is not None and nb in self.knownDeadEnds and nb not in self.remainingBones and nb not in self.ends:
                self.deadEndEdges.add((int(pos[0]), int(pos[1]), int(act)))

    def _discoveredGraphDistanceToFrontier(self, startCell):
        """Compute shortest path distance within the DISCOVERED graph from `startCell`
        to the nearest unvisited discovered cell (or visible Bone/End).

        Uses ONLY cells in `self.visitCounts` and their observed open neighbors in
        `self.discoveredCells`. Never accesses any hidden or undiscovered cell.
        Returns (distance, targetFrontierCell) or (None, None) if no frontier is reachable
        through known open doorways.
        """
        if startCell in self.ends or startCell in self.remainingBones:
            return 0, startCell
        if self.visitCountAt(startCell) == 0 and startCell not in self.knownDeadEnds:
            return 0, startCell

        queue = deque([(startCell, 0)])
        seen = {startCell}
        while queue:
            curr, dist = queue.popleft()
            if curr not in self.visitCounts:
                # Reached an unvisited frontier cell observed from a visited neighbor
                if curr not in self.knownDeadEnds:
                    return dist, curr
                continue
            for act in range(4):
                nb = self.neighborAt(curr, act)
                if nb is None or nb in seen:
                    continue
                if nb in self.knownDeadEnds and nb not in self.remainingBones and nb not in self.ends:
                    continue
                seen.add(nb)
                if nb in self.ends or nb in self.remainingBones or self.visitCountAt(nb) == 0:
                    return dist + 1, nb
                queue.append((nb, dist + 1))
        return None, None

    def computeNavigationActionBias(self, includeCrossAttemptMemory=True):
        """Compute an active action-selection logit bias vector [4] using ONLY
        the Dog's local observation and episodic memory.

        This ensures the action-selection system actively prevents oscillation loops,
        escapes dead ends along discovered paths, prefers unexplored junction exits,
        and navigates toward the locked score-aware objective without ever seeing the
        hidden maze.
        """
        openActions = self.availableActionIndices()
        if len(openActions) <= 1:
            return np.zeros(4, dtype=np.float32)

        pos = (int(self.position[0]), int(self.position[1]))
        navCfg = self.navConfig
        pm = self.priorMazeMemory if includeCrossAttemptMemory else {}
        priorDeadEdges = (pm.get("cumulativeDeadEndEdges", set()) if pm else set()) | self.deadEndEdges
        priorLoopEdges = (pm.get("historicalLoopEdges", set()) if pm else set()) | self.loopEdges
        priorEdges = pm.get("cumulativeTraversedEdges", set()) if pm else set()

        bias = np.zeros(4, dtype=np.float32)
        activeTarget = self.currentTarget if self.currentTarget is not None else self._nearestEnd(pos)
        currTargetDist = self._manhattan(pos, activeTarget)
        nearestEnd = self._nearestEnd(pos)
        currEndDist = self._manhattan(pos, nearestEnd)

        deadActions = []
        viableActions = []
        for act in openActions:
            target = self.neighbor(act)
            if target is None:
                continue
            edgeTuple = (pos[0], pos[1], int(act))
            isDead = (
                (target in self.knownDeadEnds or edgeTuple in priorDeadEdges)
                and (target not in self.remainingBones)
                and (target not in self.ends)
            )
            if isDead:
                deadActions.append(act)
            else:
                viableActions.append(act)

        # 1. Immediate adjacent End or Bone override
        # Prefer collecting an adjacent dead-end/pocket Bone before continuing down the main corridor
        hasAdjacentPocketBone = any(
            self.neighbor(a) in self.remainingBones
            and sum(1 for d in range(4) if self.neighborAt(self.neighbor(a), d) is not None) <= 1
            for a in openActions
            if self.neighbor(a) is not None
        )
        for act in openActions:
            target = self.neighbor(act)
            if target is None:
                continue
            if target in self.ends:
                # If no bones adjacent or remaining, End is highest priority
                bias[act] += 18.0 if not self.remainingBones else 12.0
            elif target in self.remainingBones:
                isPocketBone = sum(1 for d in range(4) if self.neighborAt(target, d) is not None) <= 1
                bias[act] += 18.0 if (isPocketBone and hasAdjacentPocketBone) else 15.0

        # 2. Dead-end suppression when at least one non-dead-end exit exists
        if deadActions and viableActions:
            for act in deadActions:
                bias[act] -= float(navCfg.get("deadEndAvoidanceBias", 7.5))

        candidatePool = viableActions if viableActions else openActions

        # 3. Oscillation shield & recent-reversal suppression
        prevPos = tuple(self.positionHistory[-2]) if len(self.positionHistory) >= 2 else None
        pos3Ago = tuple(self.positionHistory[-3]) if len(self.positionHistory) >= 3 else None

        for act in candidatePool:
            target = self.neighbor(act)
            if target is None:
                continue
            edgeTuple = (pos[0], pos[1], int(act))
            edgeVisits = self.edgeCounts.get((pos, act), 0)
            cellVisits = self.visitCountAt(target)

            # Escalating penalty for already-visited cells and repeated directed doorways
            if cellVisits > 0:
                bias[act] -= float(navCfg.get("revisitAvoidanceScale", 2.4)) * min(cellVisits, 4)
            if edgeVisits > 0:
                bias[act] -= float(navCfg.get("edgeRepeatAvoidanceScale", 2.6)) * min(edgeVisits, 4)

            # Strong suppression against immediate back-step (pos -> prevPos) when other viable exits exist,
            # UNLESS we just collected a Bone at `pos` (escaping a 1-step Bone pocket)
            if prevPos is not None and target == prevPos and len(candidatePool) > 1 and not self.lastBoneCollected:
                bias[act] -= 4.2
                # If stepping to prevPos would complete an A -> B -> A -> B oscillation, block it strongly
                if pos3Ago is not None and pos == pos3Ago:
                    bias[act] -= float(navCfg.get("oscillationShieldBias", 9.0))

            # Suppress known loop edges
            if edgeTuple in priorLoopEdges and cellVisits > 0 and len(candidatePool) > 1:
                bias[act] -= 4.5

            # Unexplored doorway & cell bonus + objective alignment
            if cellVisits == 0 and edgeVisits == 0:
                bias[act] += float(navCfg.get("unexploredFrontierBonus", 2.2))
                if priorEdges and edgeTuple not in priorEdges:
                    bias[act] += 0.65

            # Resolve known pit destination if already discovered in this episode
            effectivePos = self.discoveredPitTargets.get(target, target)
            nextTargetDist = self._manhattan(effectivePos, activeTarget)
            nextEndDist = self._manhattan(effectivePos, nearestEnd)

            pullScale = float(navCfg.get("objectivePullScale", 3.2))
            if nextTargetDist < currTargetDist:
                # Moving closer to locked objective; scale down if cell is already heavily visited
                visitDamp = 1.0 / (1.0 + 0.85 * cellVisits)
                bias[act] += pullScale * visitDamp
            elif nextTargetDist > currTargetDist and cellVisits > 0:
                bias[act] -= 1.25

            if self.currentTargetType == "end" and nextEndDist < currEndDist and cellVisits == 0:
                bias[act] += 0.85

        # 4. Discovered-frontier routing when all immediate neighbors have already been visited
        if all(self.visitCountAt(self.neighbor(a)) > 0 for a in candidatePool):
            frontierDistances = {}
            for act in candidatePool:
                target = self.neighbor(act)
                if target is not None:
                    fDist, _ = self._discoveredGraphDistanceToFrontier(target)
                    if fDist is not None:
                        frontierDistances[act] = fDist
            if frontierDistances:
                minFDist = min(frontierDistances.values())
                for act, fDist in frontierDistances.items():
                    if fDist == minFDist:
                        bias[act] += 3.8
                    else:
                        bias[act] -= min(3.0, 0.75 * (fDist - minFDist))

        return bias

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
            "oscillationsDetected": int(self.oscillationsDetected),
            "immediateReversals": int(self.immediateReversalsCount),
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
        """Official score: Steps - 5 * Bones Collected."""
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
            firstPit = self.position
            pitEntered = list(self.position)
            self.discoveredPits.add(self.position)
            seenPits = set()
            while self.position in self.pits and self.position not in seenPits:
                seenPits.add(self.position)
                self.discoveredPits.add(self.position)
                self.pitVisitCounts[self.position] = self.pitVisitCounts.get(self.position, 0) + 1
                self.position = self.pits[self.position]
                teleported = True
            self.discoveredPitTargets[firstPit] = self.position

        openFromPrev = [a for a in range(4) if self.neighborAt(previousPosition, a) is not None]
        nonDeadFromPrev = [
            a
            for a in openFromPrev
            if self.neighborAt(previousPosition, a) not in priorKnownDeadEnds
            and (int(previousPosition[0]), int(previousPosition[1]), int(a)) not in priorDeadEndEdges
        ]

        # Check if the Dog avoided a known dead-end or loop edge at `previousPosition`
        avoidedMistake = False
        if moved and len(openFromPrev) >= 2:
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
        lastSeenAtStep = None
        if moved:
            priorVisits = self.visitCounts.get(self.position, 0)
            lastSeenAtStep = self.lastVisitedStep.get(self.position, None)
            self.visitCounts[self.position] = priorVisits + 1
            if priorVisits > 0:
                self.revisits += 1
        else:
            self.wallBumps += 1
        newCell = moved and priorVisits == 0
        revisit = moved and priorVisits > 0
        visitNumber = self.visitCounts.get(self.position, 1)

        self.steps += 1
        if moved:
            self.lastVisitedStep[self.position] = self.steps
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
                or (int(previousPosition[0]), int(previousPosition[1]), int(actionIndex)) in priorDeadEndEdges
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

        # Detect immediate reversal (A -> B -> A) when B was not a 1-exit dead end
        immediateReversal = bool(
            moved
            and not bone
            and len(self.positionHistory) >= 3
            and self.positionHistory[-1] == self.positionHistory[-3]
            and len(nonDeadFromPrev) >= 2
        )
        if immediateReversal:
            self.immediateReversalsCount += 1

        # Detect 2-block oscillation (A -> B -> A -> B), 3-block loop (A -> B -> C -> A), and repeated sequences
        twoBlockOscillation = bool(
            moved
            and not bone
            and not newCell
            and len(self.positionHistory) >= 4
            and self.positionHistory[-1] == self.positionHistory[-3]
            and self.positionHistory[-2] == self.positionHistory[-4]
            and len(openFromPrev) >= 2
        )
        threeBlockLoop = bool(
            moved
            and not bone
            and not newCell
            and len(self.positionHistory) >= 5
            and self.positionHistory[-1] == self.positionHistory[-4]
            and self.positionHistory[-2] == self.positionHistory[-5]
            and len(openFromPrev) >= 2
        )
        repeatedSequence = bool(twoBlockOscillation or threeBlockLoop)
        self.oscillationActive = repeatedSequence
        if repeatedSequence:
            self.repeatedSequencesCount += 1
            self.oscillationsDetected += 1
            self.loopEdges.add((int(previousPosition[0]), int(previousPosition[1]), int(actionIndex)))
            self.loopPaths.append({
                "step": self.steps,
                "from": list(previousPosition),
                "to": list(self.position),
                "type": "two_block_oscillation" if twoBlockOscillation else "three_block_loop",
            })

        repeatedCorridor = False
        if moved and not bone and priorEdgeCount >= 1:
            if priorEdgeCount >= 2:
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
            self.targetStallSteps = 0
        elif not moved:
            self.lastObjectiveProgress = -1.0
            self.noProgressStreak += 1
            self.targetStallSteps += 1
        elif distAfter < distBefore:
            self.lastObjectiveProgress = 1.0
            self.noProgressStreak = 0
            if self.minDistToCurrentTarget is None or distAfter < self.minDistToCurrentTarget:
                self.targetStallSteps = 0
            else:
                self.targetStallSteps += 1
        elif distAfter > distBefore:
            self.lastObjectiveProgress = -1.0
            self.targetStallSteps += 1
            if not newCell:
                self.noProgressStreak += 1
                if self.minDistToCurrentTarget is not None and distBefore <= 2 and distAfter >= self.minDistToCurrentTarget + 2:
                    self.unsuccessfulObjectiveAttempts += 1
            else:
                self.noProgressStreak = 0
        else:
            self.lastObjectiveProgress = 0.0
            self.targetStallSteps += 1
            if not newCell:
                self.noProgressStreak += 1

        self.lastStepWasMistake = bool(
            enteredKnownDeadEnd or repeatedSequence or repeatedCorridor or immediateReversal or (not moved)
        )
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

        # --- Rebuilt Score-Aligned Reward Calculation ---
        breakdown = {"move": float(rc.movePenalty)}
        if not moved:
            breakdown["wall"] = float(rc.wallPenalty)
        if newCell and getattr(rc, "noveltyReward", 0.0) != 0.0:
            breakdown["novelty"] = float(rc.noveltyReward)
        if revisit:
            breakdown["revisit"] = float(rc.revisitPenaltyFor(priorVisits))
            if lastSeenAtStep is not None and (self.steps - lastSeenAtStep) <= 4 and not bone and not won:
                recentPen = float(getattr(rc, "recentRevisitPenalty", 0.0))
                if recentPen != 0.0:
                    breakdown["recentRevisit"] = recentPen
            if priorEdgeCount >= 1 and not bone and not won:
                edgePen = float(getattr(rc, "edgeRepeatPenalty", 0.0)) * min(priorEdgeCount, 3)
                if edgePen != 0.0:
                    breakdown["edgeRepeat"] = edgePen
            if immediateReversal and not repeatedSequence and getattr(rc, "reversePenalty", 0.0) != 0.0:
                breakdown["reverse"] = float(rc.reversePenalty)
            if repeatedSequence and getattr(rc, "oscillationPenalty", 0.0) != 0.0:
                breakdown["oscillation"] = float(rc.oscillationPenalty)
            if enteredKnownDeadEnd and getattr(rc, "deadEndPenalty", 0.0) != 0.0:
                breakdown["deadEnd"] = float(rc.deadEndPenalty)
            if repeatedCorridor and getattr(rc, "loopPenalty", 0.0) != 0.0:
                breakdown["mistake"] = float(rc.loopPenalty)

        # Objective progress shaping (only when moving without collecting bone/end on this step)
        if moved and not bone and not won:
            if distAfter < distBefore and not revisit and getattr(rc, "progressReward", 0.0) != 0.0:
                breakdown["progress"] = float(rc.progressReward)
            elif distAfter > distBefore and revisit and len(nonDeadFromPrev) >= 2 and getattr(rc, "regressPenalty", 0.0) != 0.0:
                breakdown["regress"] = float(rc.regressPenalty)

        if bone:
            breakdown["bone"] = float(rc.boneReward)
            if completedAllFive:
                extraFifth = float(stepBoneReward - rc.boneReward)
                if extraFifth != 0.0:
                    breakdown["allBones"] = extraFifth
        if won:
            breakdown["end"] = float(rc.endReward)
            effScale = float(getattr(rc, "efficiencyBonusScale", 0.0))
            if effScale > 0.0:
                # Higher efficiency bonus for lower official score
                effFactor = max(0.0, min(1.5, (60.0 - float(officialScore)) / 60.0))
                breakdown["efficiency"] = round(effScale * effFactor, 4)
        elif scoreLimitExceeded:
            breakdown["scoreLimit"] = float(rc.scoreLimitPenalty)
            breakdown["failure"] = float(rc.failurePenalty)
        elif timeout:
            breakdown["stepLimit"] = float(rc.stepLimitPenalty)
            breakdown["failure"] = float(rc.failurePenalty)

        reward = float(sum(breakdown.values()))

        # Official-score-aligned signal (negated official score delta: -1 per step, +5 per bone)
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
            "enteredDeadEnd": enteredKnownDeadEnd or newlyFoundDeadEnd,
            "deadEndsEncountered": self.deadEndsEncountered,
            "deadEndReentries": self.deadEndReentries,
            "oscillationDetected": repeatedSequence,
            "oscillationsDetected": self.oscillationsDetected,
            "immediateReversals": self.immediateReversalsCount,
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
            "oscillationsDetected": self.oscillationsDetected,
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

