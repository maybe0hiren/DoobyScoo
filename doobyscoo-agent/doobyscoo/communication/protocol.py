import numpy as np
from ..environment.maze_environment import ACTION_NAMES, NAME_TO_ACTION
from ..environment.observation import OBSERVATION_SIZE, LEGACY_OBSERVATION_SIZE


def parseActionValue(action):
    if isinstance(action, str):
        key = action.strip().lower()
        if key not in NAME_TO_ACTION:
            raise ValueError(f"Invalid action name: {action}")
        return NAME_TO_ACTION[key]
    idx = int(action)
    if idx not in range(4):
        raise ValueError(f"Action index out of range: {action}")
    return idx


def actionToName(actionIndex):
    idx = parseActionValue(actionIndex)
    return ACTION_NAMES[idx]


def validateObservationInput(observation, sessionObservation=None):
    if observation is None:
        raise ValueError("Observation cannot be None")
    arr = np.asarray(observation, dtype=np.float32).reshape(-1)
    if not np.all(np.isfinite(arr)):
        raise ValueError("Observation contains NaN or infinite values")
    if arr.shape[0] == OBSERVATION_SIZE:
        return arr
    if arr.shape[0] == LEGACY_OBSERVATION_SIZE:
        if sessionObservation is not None and len(sessionObservation) == OBSERVATION_SIZE:
            merged = np.asarray(sessionObservation, dtype=np.float32).copy()
            merged[:LEGACY_OBSERVATION_SIZE] = arr
            return merged
        padded = np.zeros(OBSERVATION_SIZE, dtype=np.float32)
        padded[:LEGACY_OBSERVATION_SIZE] = arr
        return padded
    raise ValueError(f"Expected {OBSERVATION_SIZE}-feature observation (or {LEGACY_OBSERVATION_SIZE} legacy), got {arr.shape[0]}")
