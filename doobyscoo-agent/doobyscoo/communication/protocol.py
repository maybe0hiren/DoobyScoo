import numpy as np
from ..environment.maze_environment import ACTION_NAMES, NAME_TO_ACTION
from ..environment.observation import OBSERVATION_SIZE


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


def validateObservationInput(observation):
    if observation is None:
        raise ValueError("Observation cannot be None")
    arr = np.asarray(observation, dtype=np.float32).reshape(-1)
    if arr.shape[0] != OBSERVATION_SIZE:
        raise ValueError(f"Expected {OBSERVATION_SIZE}-feature observation, got {arr.shape[0]}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("Observation contains NaN or infinite values")
    return arr

