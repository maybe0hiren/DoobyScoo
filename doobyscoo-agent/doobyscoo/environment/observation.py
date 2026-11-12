"""Partial observation encoder.

The Dog only perceives its four adjacent squares, its current square, and its own
episodic memory (how often it has visited each adjacent square, how often it has
traversed each doorway out of the current square, its previous action, whether it
just bumped a wall, and elapsed time). The global layout, positions of distant
bones/ends, and any shortest-path information are never exposed.

Layout (OBSERVATION_SIZE = 23):
  0-3   neighbour type UP/DOWN/LEFT/RIGHT  (BLOCKED=0, EMPTY=1, BONE=2, END=3, PIT=4) / 4
  4     current square is a pit / just teleported
  5     bone collected on this square
  6     current square is an End
  7     remaining bones / total bones
  8-11  visit level of neighbour UP/DOWN/LEFT/RIGHT: min(visits, 4) / 4
        (0 = unexplored, 0.25 = visited once, 0.5 = twice, 0.75 = 3x, 1.0 = 4+; 0 when blocked)
  12    visit level of the current square: min(visits, 4) / 4
  13-16 doorway traversal level UP/DOWN/LEFT/RIGHT from current square: min(edgeVisits, 4) / 4
  17-20 one-hot previous action (all zero on the first step)
  21    previous action bumped into a wall
  22    elapsed steps / maxSteps
"""
import numpy as np

OBS_BLOCKED = 0
OBS_EMPTY = 1
OBS_BONE = 2
OBS_END = 3
OBS_PIT = 4

LEGACY_OBSERVATION_SIZE = 8
OBSERVATION_SIZE = 23
VISIT_LEVEL_CAP = 4.0


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

        return np.asarray(
            directional
            + [currentIsPit, currentIsBone, currentIsEnd, remainingNorm]
            + neighbourVisits
            + [currentVisits]
            + edgeVisits
            + lastAction
            + [bumped, progress],
            dtype=np.float32,
        )

    def encode(self, env):
        raw = self.encodeRaw(env)
        if not self.normalize:
            return raw
        normalized = raw.copy()
        normalized[:4] = normalized[:4] / 4.0
        normalized[8:17] = normalized[8:17] / VISIT_LEVEL_CAP
        return normalized
