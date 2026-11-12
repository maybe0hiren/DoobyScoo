import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from ..agent.network import chooseActionsBatch
from ..environment.maze_environment import MazeEnvironment, loadMaze


def gridHash(mazeData):
    canonical = json.dumps(mazeData.get("grid", []), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


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


def _mazeName(item, index):
    if isinstance(item, (str, Path)):
        return Path(item).name
    return item.get("metadata", {}).get("maze_name", f"maze_{index}")


def collectEpisodes(model, mazes, maxSteps=300, deterministic=False, rewardConfig=None, recordTrajectory=True):
    """Roll out one episode per maze in parallel with a single batched forward pass per step.

    Each episode owns an independent zero-initialised LSTM state (reset at the
    episode boundary). Training uses deterministic=False so actions are sampled
    from the policy distribution; argmax is reserved for evaluation/competition.
    """
    mazeData = [loadMaze(m) if isinstance(m, (str, Path)) else m for m in mazes]
    envs = [MazeEnvironment(m, maxSteps=maxSteps, rewardConfig=rewardConfig) for m in mazeData]
    count = len(envs)
    if count == 0:
        return []
    episodes = [
        {
            "observations": [],
            "actions": [],
            "logProbs": [],
            "values": [],
            "rewards": [],
            "rawRewards": [],
            "entropies": [],
            "sourceMap": _mazeName(mazes[i], i),
            "mapHash": gridHash(mazeData[i]),
            "deterministic": bool(deterministic),
        }
        for i in range(count)
    ]
    observations = [env.reset() for env in envs]
    lastInfo = [None] * count
    active = list(range(count))
    state = model.initialState(batchSize=count)
    wasTraining = model.training
    model.eval()
    with torch.no_grad():
        while active:
            obsBatch = np.stack([observations[i] for i in active])
            subState = state if len(active) == count else state._withTensors(state.h[active], state.c[active])
            actions, logProbs, values, entropies, nextState = chooseActionsBatch(model, obsBatch, subState, deterministic)
            if len(active) == count:
                state = nextState
            else:
                state.h = state.h.clone()
                state.c = state.c.clone()
                state.h[active] = nextState.h
                state.c[active] = nextState.c
            stillActive = []
            for j, i in enumerate(active):
                action = int(actions[j])
                nextObs, reward, done, info = envs[i].step(action)
                ep = episodes[i]
                if recordTrajectory:
                    ep["observations"].append(observations[i])
                    ep["logProbs"].append(float(logProbs[j]))
                    ep["values"].append(float(values[j]))
                    ep["entropies"].append(float(entropies[j]))
                ep["actions"].append(action)
                ep["rewards"].append(reward)
                ep["rawRewards"].append(info["rawReward"])
                observations[i] = nextObs
                lastInfo[i] = info
                if not done:
                    stillActive.append(i)
            active = stillActive
    if wasTraining:
        model.train()

    for i, ep in enumerate(episodes):
        info = lastInfo[i] or {}
        env = envs[i]
        ep["initialState"] = None
        ep["bootstrapValue"] = 0.0
        ep["won"] = bool(info.get("won", False))
        ep["timeout"] = bool(info.get("timeout", False))
        ep["score"] = int(info.get("score", 0))
        ep["bonesCollected"] = int(info.get("bonesCollected", 0))
        ep["totalBones"] = len(env.bones)
        ep["length"] = len(ep["actions"])
        ep["revisits"] = int(env.revisits)
        ep["wallBumps"] = int(env.wallBumps)
        ep["uniqueCells"] = len(env.visitCounts)
        ep["totalReward"] = float(sum(ep["rewards"]))
        ep["rawTotalReward"] = float(sum(ep["rawRewards"]))
        ep["meanEntropy"] = float(np.mean(ep["entropies"])) if ep["entropies"] else 0.0
    return episodes


def collectEpisode(model, mazeData, maxSteps=300, deterministic=False, rewardConfig=None):
    return collectEpisodes(model, [mazeData], maxSteps=maxSteps, deterministic=deterministic, rewardConfig=rewardConfig)[0]
