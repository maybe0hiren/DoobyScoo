"""Partial observation encoder with 5x5 local view, legal action masking,
dead-end/junction topology awareness, episodic exploration & oscillation memory,
and score-aware 5-Bone + End objective awareness.

Strict partial observability is preserved at all times:
  - The Dog never receives the complete maze layout, hidden walls, unexplored
    corridors, undiscovered pits, or oracle shortest-path routes.
  - All topological knowledge (knownDeadEnds, knownJunctions, discoveredCells,
    edgeCounts, visitCounts, oscillation flags) comes exclusively from the
    Dog's actual experience during the current episode.

Layout (OBSERVATION_SIZE = 95):
  0-3   neighbour type UP/DOWN/LEFT/RIGHT  (BLOCKED=0, EMPTY=1, BONE=2, END=3, PIT=4) / 4
  4     current square is a pit / just teleported
  5     bone collected on this square
  6     current square is an End
  7     remaining bones / total bones
  8-11  visit level of neighbour UP/DOWN/LEFT/RIGHT: min(visits, 4) / 4
  12    visit level of the current square: min(visits, 4) / 4
  13-16 doorway traversal level UP/DOWN/LEFT/RIGHT from current square: min(edgeVisits, 4) / 4
  17-20 one-hot previous action (all zero on the first step)
  21    previous action bumped into a wall
  22    elapsed steps / maxSteps
  23-37 5 Bone slots (Bone 1..5), 3 features each:
          [23 + 3*i + 0]: horizontal displacement (bx - x), normalized by (width - 1) in [-1, 1]
          [23 + 3*i + 1]: vertical displacement (by - y), normalized by (height - 1) in [-1, 1]
          [23 + 3*i + 2]: collected flag (0.0 = not collected, 1.0 = already collected)
  38-62 5x5 local view (25 cells, row-major dy in -2..2, dx in -2..2, centre at index 50):
          codes (BLOCKED=0, EMPTY=1, BONE=2, END=3, PIT=4, UNKNOWN=5) normalized by / 5
  63-66 4-direction legal action mask (UP, DOWN, LEFT, RIGHT) in {0.0, 1.0}
  67-82 Local navigation structure (16 features):
          67:    isDeadEnd
          68:    isCorridor
          69:    isJunction
          70:    hasMultipleExits
          71-74: exploredExits UP/DOWN/LEFT/RIGHT
          75-78: unexploredExits UP/DOWN/LEFT/RIGHT
          79-82: deadEndExits UP/DOWN/LEFT/RIGHT
  83-88 Episodic exploration & oscillation memory (6 features):
          83: visitedCells / totalCells
          84: discoveredCells / totalCells
          85: knownDeadEnds / visitedCells
          86: knownJunctions / visitedCells
          87: oscillation / loopMistakeActive flag
          88: normalized no-progress streak
  89-94 Objective distance & progress awareness (6 features):
          89: nearest End dx normalized in [-1, 1]
          90: nearest End dy normalized in [-1, 1]
          91: nearest End Manhattan distance normalized in [0, 1]
          92: active locked objective dx normalized in [-1, 1]
          93: active locked objective dy normalized in [-1, 1]
          94: latest step objective progress in [-1, 1]
"""
import numpy as np

OBS_BLOCKED = 0
OBS_EMPTY = 1
OBS_BONE = 2
OBS_END = 3
OBS_PIT = 4
OBS_UNKNOWN = 5

LOCAL_VIEW_RADIUS = 2
LOCAL_VIEW_SIDE = 2 * LOCAL_VIEW_RADIUS + 1  # 5
LOCAL_VIEW_SIZE = LOCAL_VIEW_SIDE * LOCAL_VIEW_SIDE  # 25
LOCAL_VIEW_CENTER = (LOCAL_VIEW_RADIUS, LOCAL_VIEW_RADIUS)  # (2, 2)
LOCAL_VIEW_CENTER_INDEX = LOCAL_VIEW_RADIUS * LOCAL_VIEW_SIDE + LOCAL_VIEW_RADIUS  # 12
LOCAL_VIEW_MAX_CODE = float(OBS_UNKNOWN)  # 5.0

MAX_BONES = 5
BONE_FEATURES_PER_SLOT = 3
BONE_OBSERVATION_OFFSET = 23
LOCAL_VIEW_OFFSET = BONE_OBSERVATION_OFFSET + MAX_BONES * BONE_FEATURES_PER_SLOT  # 38
ACTION_MASK_OFFSET = LOCAL_VIEW_OFFSET + LOCAL_VIEW_SIZE  # 63
NAVIGATION_OFFSET = ACTION_MASK_OFFSET + 4  # 67
EXPLORATION_MEMORY_OFFSET = NAVIGATION_OFFSET + 16  # 83
OBJECTIVE_OFFSET = EXPLORATION_MEMORY_OFFSET + 6  # 89

LEGACY_OBSERVATION_SIZE = 8
PREVIOUS_OBSERVATION_SIZE = 23
V3_OBSERVATION_SIZE = 38
OBSERVATION_SIZE = OBJECTIVE_OFFSET + 6  # 95
VISIT_LEVEL_CAP = 4.0

_CARDINAL_OFFSET_TO_ACTION = {
    (0, -1): 0,  # UP
    (0, 1): 1,   # DOWN
    (-1, 0): 2,  # LEFT
    (1, 0): 3,   # RIGHT
}


class ObservationEncoder:
    def __init__(self, normalize=True):
        self.normalize = normalize
        self.size = OBSERVATION_SIZE

    def directionalCode(self, env, action):
        target = env.neighbor(action)
        if target is None:
            return OBS_BLOCKED
        if target in env.ends:
            return OBS_END
        if target in env.remainingBones:
            return OBS_BONE
        if target in env.pits:
            return OBS_PIT
        return OBS_EMPTY

    def _currentCellCode(self, env):
        x, y = env.position
        if env.position in env.ends:
            return OBS_END
        if env.position in env.remainingBones or getattr(env, "lastBoneCollected", False):
            return OBS_BONE
        cellElement = int(env.grid[y][x].get("element", 0))
        if cellElement == 3 or getattr(env, "lastTeleported", False):
            return OBS_PIT
        return OBS_EMPTY

    def encodeLocalView(self, env, normalize=False):
        """Return the 5x5 local view centred at env.position (row=2, col=2).

        Preserves strict partial observability:
          - Out-of-bounds cells are OBS_BLOCKED (0).
          - Centre (2, 2) is always the Dog's current cell.
          - Immediate cardinal neighbors reflect legal doorway visibility (OBS_BLOCKED if walled).
          - Other cells within the 5x5 window are visible only if already discovered during
            the current episode; undiscovered cells are marked OBS_UNKNOWN (5).
        """
        x, y = env.position
        discovered = getattr(env, "discoveredCells", None)
        if discovered is None:
            discovered = set(getattr(env, "visitCounts", {}).keys())
            for act in range(4):
                nb = env.neighbor(act)
                if nb is not None:
                    discovered.add(nb)
        discoveredPits = getattr(env, "discoveredPits", set())

        grid5x5 = np.full((LOCAL_VIEW_SIDE, LOCAL_VIEW_SIDE), OBS_UNKNOWN, dtype=np.float32)
        for row in range(LOCAL_VIEW_SIDE):
            dy = row - LOCAL_VIEW_RADIUS
            cy = y + dy
            for col in range(LOCAL_VIEW_SIDE):
                dx = col - LOCAL_VIEW_RADIUS
                cx = x + dx
                if dx == 0 and dy == 0:
                    grid5x5[row, col] = float(self._currentCellCode(env))
                    continue
                if not env.inside((cx, cy)):
                    grid5x5[row, col] = float(OBS_BLOCKED)
                    continue
                if abs(dx) + abs(dy) == 1:
                    act = _CARDINAL_OFFSET_TO_ACTION[(dx, dy)]
                    grid5x5[row, col] = float(self.directionalCode(env, act))
                    continue
                pos = (cx, cy)
                if pos in discovered:
                    if pos in env.ends:
                        grid5x5[row, col] = float(OBS_END)
                    elif pos in env.remainingBones:
                        grid5x5[row, col] = float(OBS_BONE)
                    elif pos in discoveredPits:
                        grid5x5[row, col] = float(OBS_PIT)
                    else:
                        grid5x5[row, col] = float(OBS_EMPTY)
                else:
                    grid5x5[row, col] = float(OBS_UNKNOWN)

        if normalize:
            return grid5x5 / LOCAL_VIEW_MAX_CODE
        return grid5x5

    def encodeActionMask(self, env):
        """Return 4-direction legal action mask [UP, DOWN, LEFT, RIGHT] in {0.0, 1.0}."""
        return np.asarray(
            [1.0 if env.neighbor(action) is not None else 0.0 for action in range(4)],
            dtype=np.float32,
        )

    def encodeNavigation(self, env):
        """Compute local dead-end, corridor, junction, and exit status from discovered info only."""
        knownDeadEnds = getattr(env, "knownDeadEnds", set())
        deadEndEdges = getattr(env, "deadEndEdges", set())
        edgeCounts = getattr(env, "edgeCounts", {})
        pos = env.position

        openMask = [env.neighbor(a) is not None for a in range(4)]
        openCount = sum(1 for flag in openMask if flag)

        exploredExits = []
        unexploredExits = []
        deadEndExits = []
        nonDeadEndOpenCount = 0

        for action in range(4):
            target = env.neighbor(action)
            if target is None:
                exploredExits.append(0.0)
                unexploredExits.append(0.0)
                deadEndExits.append(0.0)
                continue
            edgeTraversed = edgeCounts.get((pos, action), 0) > 0
            targetVisited = env.visitCountAt(target) > 0
            isExplored = bool(edgeTraversed or targetVisited)
            edgeTuple = (int(pos[0]), int(pos[1]), int(action))
            isDeadEndBranch = bool(
                (target in knownDeadEnds or edgeTuple in deadEndEdges)
                and target not in env.remainingBones
                and target not in env.ends
            )
            if not isDeadEndBranch:
                nonDeadEndOpenCount += 1
            exploredExits.append(1.0 if isExplored else 0.0)
            unexploredExits.append(0.0 if isExplored else 1.0)
            deadEndExits.append(1.0 if isDeadEndBranch else 0.0)

        isDeadEnd = bool(openCount <= 1 or pos in knownDeadEnds or (openCount > 0 and nonDeadEndOpenCount == 0))
        isJunction = bool(openCount >= 3 and not isDeadEnd)
        isCorridor = bool(openCount == 2 and not isDeadEnd)
        hasMultipleExits = bool(openCount >= 2)

        return {
            "isDeadEnd": isDeadEnd,
            "isCorridor": isCorridor,
            "isJunction": isJunction,
            "hasMultipleExits": hasMultipleExits,
            "openExitsCount": int(openCount),
            "nonDeadEndExitsCount": int(nonDeadEndOpenCount),
            "exploredExits": exploredExits,
            "unexploredExits": unexploredExits,
            "deadEndExits": deadEndExits,
            "vector": np.asarray(
                [
                    1.0 if isDeadEnd else 0.0,
                    1.0 if isCorridor else 0.0,
                    1.0 if isJunction else 0.0,
                    1.0 if hasMultipleExits else 0.0,
                ]
                + exploredExits
                + unexploredExits
                + deadEndExits,
                dtype=np.float32,
            ),
        }

    def encodeExplorationMemory(self, env):
        """Encode episodic discovery and oscillation/mistake indicators in [0.0, 1.0]."""
        totalCells = float(max(1, env.width * env.height))
        visitedCount = float(len(getattr(env, "visitCounts", {})))
        discoveredCount = float(len(getattr(env, "discoveredCells", getattr(env, "visitCounts", {}))))
        knownDeadEndsCount = float(len(getattr(env, "knownDeadEnds", ())))
        knownJunctionsCount = float(len(getattr(env, "knownJunctions", ())))

        visitedRatio = min(1.0, visitedCount / totalCells)
        discoveredRatio = min(1.0, discoveredCount / totalCells)
        deadEndRatio = min(1.0, knownDeadEndsCount / max(1.0, visitedCount))
        junctionRatio = min(1.0, knownJunctionsCount / max(1.0, visitedCount))
        loopMistakeActive = 1.0 if bool(getattr(env, "lastStepWasMistake", False) or getattr(env, "oscillationActive", False)) else 0.0
        noProgressNorm = min(1.0, float(getattr(env, "noProgressStreak", 0)) / 8.0)

        return np.asarray(
            [
                visitedRatio,
                discoveredRatio,
                deadEndRatio,
                junctionRatio,
                loopMistakeActive,
                noProgressNorm,
            ],
            dtype=np.float32,
        )

    def encodeBones(self, env):
        """Return structured relative positional information for all 5 Bone slots."""
        x, y = env.position
        spanX = float(max(1, env.width - 1))
        spanY = float(max(1, env.height - 1))
        orderedBones = getattr(env, "orderedBones", None)
        if orderedBones is None:
            orderedBones = sorted(env.bones, key=lambda pos: (pos[1], pos[0]))
        boneEntries = []
        for idx in range(MAX_BONES):
            if idx < len(orderedBones):
                bx, by = orderedBones[idx]
                collected = (bx, by) not in env.remainingBones
                dx = 0.0 if collected else float(bx - x)
                dy = 0.0 if collected else float(by - y)
                dxNorm = dx / spanX
                dyNorm = dy / spanY
                boneEntries.append({
                    "boneIndex": idx + 1,
                    "present": True,
                    "position": [int(bx), int(by)],
                    "dx": dx,
                    "dy": dy,
                    "dxNorm": dxNorm,
                    "dyNorm": dyNorm,
                    "collected": bool(collected),
                })
            else:
                boneEntries.append({
                    "boneIndex": idx + 1,
                    "present": False,
                    "position": None,
                    "dx": 0.0,
                    "dy": 0.0,
                    "dxNorm": 0.0,
                    "dyNorm": 0.0,
                    "collected": True,
                })
        return boneEntries

    def encodeObjectives(self, env):
        """Encode geometric distance/direction to nearest End, locked objective, and step progress.
        Never uses hidden maze shortest paths.
        """
        x, y = env.position
        spanX = float(max(1, env.width - 1))
        spanY = float(max(1, env.height - 1))
        maxManhattan = float(max(1, (env.width - 1) + (env.height - 1)))

        sortedEnds = sorted(env.ends, key=lambda pos: (abs(pos[0] - x) + abs(pos[1] - y), pos[1], pos[0]))
        nearestEnd = sortedEnds[0]
        endDx = float(nearestEnd[0] - x)
        endDy = float(nearestEnd[1] - y)
        endDxNorm = float(np.clip(endDx / spanX, -1.0, 1.0))
        endDyNorm = float(np.clip(endDy / spanY, -1.0, 1.0))
        endDistNorm = float(np.clip((abs(endDx) + abs(endDy)) / maxManhattan, 0.0, 1.0))

        activeTarget = getattr(env, "currentTarget", None)
        targetType = getattr(env, "currentTargetType", "bone")
        if activeTarget is None or (targetType == "bone" and activeTarget not in env.remainingBones):
            if env.remainingBones:
                remSorted = sorted(env.remainingBones, key=lambda pos: (abs(pos[0] - x) + abs(pos[1] - y), pos[1], pos[0]))
                activeTarget = remSorted[0]
                targetType = "bone"
            else:
                activeTarget = nearestEnd
                targetType = "end"

        targetDx = float(activeTarget[0] - x)
        targetDy = float(activeTarget[1] - y)
        targetDxNorm = float(np.clip(targetDx / spanX, -1.0, 1.0))
        targetDyNorm = float(np.clip(targetDy / spanY, -1.0, 1.0))
        targetDistNorm = float(np.clip((abs(targetDx) + abs(targetDy)) / maxManhattan, 0.0, 1.0))
        progress = float(np.clip(getattr(env, "lastObjectiveProgress", 0.0), -1.0, 1.0))

        return {
            "nearestEnd": [int(nearestEnd[0]), int(nearestEnd[1])],
            "endDx": endDx,
            "endDy": endDy,
            "endDxNorm": endDxNorm,
            "endDyNorm": endDyNorm,
            "endDistNorm": endDistNorm,
            "activeObjective": {
                "type": targetType,
                "position": [int(activeTarget[0]), int(activeTarget[1])],
                "dx": targetDx,
                "dy": targetDy,
                "dxNorm": targetDxNorm,
                "dyNorm": targetDyNorm,
                "distNorm": targetDistNorm,
            },
            "objectiveProgress": progress,
            "madeProgress": bool(progress > 0.0),
            "vector": np.asarray(
                [endDxNorm, endDyNorm, endDistNorm, targetDxNorm, targetDyNorm, progress],
                dtype=np.float32,
            ),
        }

    def encodeRaw(self, env):
        directional = [float(self.directionalCode(env, action)) for action in range(4)]
        x, y = env.position
        cellElement = int(env.grid[y][x].get("element", 0))
        currentIsPit = float(cellElement == 3 or getattr(env, "lastTeleported", False))
        currentIsBone = float(env.position in env.remainingBones or getattr(env, "lastBoneCollected", False))
        currentIsEnd = float(env.position in env.ends)
        totalBones = len(env.bones)
        remainingNorm = float(len(env.remainingBones)) / float(totalBones) if totalBones else 0.0

        neighbourVisits = []
        edgeVisits = []
        edgeDict = getattr(env, "edgeCounts", {})
        for action in range(4):
            target = env.neighbor(action)
            neighbourVisits.append(0.0 if target is None else float(min(env.visitCountAt(target), VISIT_LEVEL_CAP)))
            edgeVisits.append(float(min(edgeDict.get((env.position, action), 0), VISIT_LEVEL_CAP)))
        currentVisits = float(min(env.visitCounts.get(env.position, 0), VISIT_LEVEL_CAP))

        lastAction = [0.0, 0.0, 0.0, 0.0]
        if env.lastAction is not None:
            lastAction[int(env.lastAction)] = 1.0
        bumped = float(env.lastAction is not None and not env.lastMoved)
        progress = min(1.0, float(env.steps) / float(max(1, env.maxSteps)))

        boneFeatures = []
        for entry in self.encodeBones(env):
            boneFeatures.extend([
                float(entry["dx"]),
                float(entry["dy"]),
                1.0 if entry["collected"] else 0.0,
            ])

        localViewFlat = self.encodeLocalView(env, normalize=False).reshape(-1).tolist()
        actionMask = self.encodeActionMask(env).tolist()
        navFeatures = self.encodeNavigation(env)["vector"].tolist()
        memFeatures = self.encodeExplorationMemory(env).tolist()
        objFeatures = self.encodeObjectives(env)["vector"].tolist()

        return np.asarray(
            directional
            + [currentIsPit, currentIsBone, currentIsEnd, remainingNorm]
            + neighbourVisits
            + [currentVisits]
            + edgeVisits
            + lastAction
            + [bumped, progress]
            + boneFeatures
            + localViewFlat
            + actionMask
            + navFeatures
            + memFeatures
            + objFeatures,
            dtype=np.float32,
        )

    def encode(self, env):
        raw = self.encodeRaw(env)
        if not self.normalize:
            return raw
        normalized = raw.copy()
        normalized[:4] = normalized[:4] / 4.0
        normalized[8:17] = normalized[8:17] / VISIT_LEVEL_CAP
        spanX = float(max(1, env.width - 1))
        spanY = float(max(1, env.height - 1))
        for idx in range(MAX_BONES):
            base = BONE_OBSERVATION_OFFSET + idx * BONE_FEATURES_PER_SLOT
            normalized[base] = normalized[base] / spanX
            normalized[base + 1] = normalized[base + 1] / spanY
        normalized[LOCAL_VIEW_OFFSET : LOCAL_VIEW_OFFSET + LOCAL_VIEW_SIZE] = (
            normalized[LOCAL_VIEW_OFFSET : LOCAL_VIEW_OFFSET + LOCAL_VIEW_SIZE] / LOCAL_VIEW_MAX_CODE
        )
        return normalized

