import numpy as np

OBS_BLOCKED = 0
OBS_EMPTY = 1
OBS_BONE = 2
OBS_END = 3
OBS_PIT = 4

OBSERVATION_SIZE = 8


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
        totalBones = max(1, len(env.bones)) if env.bones else 5
        remainingNorm = float(len(env.remainingBones)) / float(totalBones)
        return np.asarray(directional + [currentIsPit, currentIsBone, currentIsEnd, remainingNorm], dtype=np.float32)

    def encode(self, env):
        raw = self.encodeRaw(env)
        if not self.normalize:
            return raw
        normalized = raw.copy()
        normalized[:4] = normalized[:4] / 4.0
        return normalized

