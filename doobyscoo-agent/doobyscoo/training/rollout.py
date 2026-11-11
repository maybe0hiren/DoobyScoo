import json
from pathlib import Path
from ..agent.network import chooseAction
from ..environment.maze_environment import MazeEnvironment, loadMaze


def discoverMaps(folder, excludedFolders=None):
    if folder is None:
        return []
    folderPath = Path(folder)
    if not folderPath.exists():
        raise ValueError(f"No valid maze JSON files in {folder}")
    excluded = [Path(f).resolve() for f in (excludedFolders or []) if f is not None]
    paths = sorted(folderPath.rglob("*.json"))
    valid = []
    for path in paths:
        resolved = path.resolve()
        if any(resolved == ex or ex in resolved.parents for ex in excluded):
            continue
        try:
            MazeEnvironment(loadMaze(path))
            valid.append(path)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            print(f"Skipping {path.name}: {error}")
    if not valid:
        raise ValueError(f"No valid maze JSON files in {folder}")
    return valid


def collectEpisode(model, mazeData, maxSteps=300, deterministic=False, rewardConfig=None):
    env = MazeEnvironment(mazeData, maxSteps=maxSteps, rewardConfig=rewardConfig)
    observation = env.reset()
    state = model.initialState()
    initialState = state.detach()
    episode = {
        "observations": [],
        "actions": [],
        "logProbs": [],
        "values": [],
        "rewards": [],
        "rawRewards": [],
        "initialState": initialState,
    }
    info = None
    for _ in range(maxSteps):
        action, logProb, value, state = chooseAction(model, observation, state, deterministic=deterministic)
        nextObservation, reward, done, info = env.step(action)
        episode["observations"].append(observation)
        episode["actions"].append(action)
        episode["logProbs"].append(logProb)
        episode["values"].append(value)
        episode["rewards"].append(reward)
        episode["rawRewards"].append(info["rawReward"])
        observation = nextObservation
        if done:
            break

    episode["bootstrapValue"] = 0.0
    episode["won"] = bool(info["won"]) if info else False
    episode["timeout"] = bool(info["timeout"]) if info else False
    episode["score"] = int(info["score"]) if info else 0
    episode["bonesCollected"] = int(info["bonesCollected"]) if info else 0
    episode["length"] = len(episode["actions"])
    episode["totalReward"] = float(sum(episode["rewards"]))
    episode["rawTotalReward"] = float(sum(episode["rawRewards"]))
    return episode
