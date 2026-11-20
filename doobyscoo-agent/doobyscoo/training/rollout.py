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


def _computeBatchNavigationBias(
    model,
    envs,
    activeIndices,
    priorEdgesByMap,
    episodes,
    bonus,
    deadEndEdgesByMap=None,
    loopEdgesByMap=None,
    bestEdgesByMap=None,
    attemptIndex=1,
    deterministic=False,
):
    """Compute per-step navigation bias for each active environment using its
    local observation and episodic memory (`computeNavigationActionBias`)."""
    if getattr(model, "isUntrainedBaseline", False):
        return None
    bias = np.zeros((len(activeIndices), 4), dtype=np.float32)
    for rowIdx, envIdx in enumerate(activeIndices):
        env = envs[envIdx]
        mapName = episodes[envIdx]["sourceMap"]
        pos = (int(env.position[0]), int(env.position[1]))

        # Base episodic navigation bias:
        # In deterministic evaluation/competition, apply full active shield + objective pull;
        # during stochastic training rollouts, scale down so the neural policy explores diverse
        # routes while still preventing endless oscillations and dead-end traps.
        envBias = env.computeNavigationActionBias(includeCrossAttemptMemory=not deterministic)
        biasScale = 1.0 if deterministic else 0.30
        bias[rowIdx] = envBias * biasScale

        openActions = env.availableActionIndices()
        if len(openActions) < 2 or deterministic:
            continue

        priorEdges = (priorEdgesByMap or {}).get(mapName) or set()
        priorDeadEdges = (deadEndEdgesByMap or {}).get(mapName) or set()
        priorLoopEdges = (loopEdgesByMap or {}).get(mapName) or set()
        bestEdges = (bestEdgesByMap or {}).get(mapName) or set()

        viableActions = [
            act
            for act in openActions
            if env.neighbor(act) is not None
            and (
                (env.neighbor(act) not in env.knownDeadEnds and (pos[0], pos[1], int(act)) not in priorDeadEdges)
                or (env.neighbor(act) in env.remainingBones)
                or (env.neighbor(act) in env.ends)
            )
        ]

        for act in viableActions:
            target = env.neighbor(act)
            edgeTuple = (pos[0], pos[1], int(act))
            if edgeTuple in priorLoopEdges and target is not None and env.visitCountAt(target) > 0:
                bias[rowIdx, act] -= 1.5

        if bonus > 0.0 and priorEdges:
            unvisitedPrior = []
            visitedPrior = []
            for act in viableActions:
                target = env.neighbor(act)
                if target is None or env.visitCountAt(target) > 0:
                    continue
                if (pos[0], pos[1], int(act)) in priorEdges:
                    visitedPrior.append(act)
                else:
                    unvisitedPrior.append(act)
            if unvisitedPrior and visitedPrior:
                for act in unvisitedPrior:
                    bias[rowIdx, act] += float(bonus)
            elif bestEdges and attemptIndex >= 2:
                for act in viableActions:
                    if (pos[0], pos[1], int(act)) in bestEdges and env.edgeCounts.get((pos, act), 0) == 0:
                        bias[rowIdx, act] += float(0.75 * max(0.35, bonus))

    return bias


def collectEpisodes(
    model,
    mazes,
    maxSteps=300,
    deterministic=False,
    rewardConfig=None,
    recordTrajectory=True,
    enforceScoreLimit=True,
    priorEdgesByMap=None,
    routeDiversityBonus=0.0,
    attemptIndex=1,
    deadEndEdgesByMap=None,
    loopEdgesByMap=None,
    bestEdgesByMap=None,
    priorMazeMemoryByMap=None,
):
    """Roll out one episode per maze in parallel with a single batched forward pass per step."""
    mazeData = [loadMaze(m) if isinstance(m, (str, Path)) else m for m in mazes]
    mapNames = [_mazeName(mazes[i], i) for i in range(len(mazeData))]
    envs = [
        MazeEnvironment(
            m,
            maxSteps=maxSteps,
            rewardConfig=rewardConfig,
            enforceScoreLimit=enforceScoreLimit,
            priorMazeMemory=(priorMazeMemoryByMap or {}).get(mapNames[i]),
        )
        for i, m in enumerate(mazeData)
    ]
    count = len(envs)
    if count == 0:
        return []
    episodes = [
        {
            "observations": [],
            "actions": [],
            "actionMasks": [],
            "logProbs": [],
            "values": [],
            "rewards": [],
            "rawRewards": [],
            "entropies": [],
            "sourceMap": mapNames[i],
            "mapHash": gridHash(mazeData[i]),
            "deterministic": bool(deterministic),
            "attemptIndex": int(attemptIndex),
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
            maskBatch = np.stack([envs[i].actionMask() for i in active])
            subState = state if len(active) == count else state._withTensors(state.h[active], state.c[active])
            logitBias = _computeBatchNavigationBias(
                model,
                envs,
                active,
                priorEdgesByMap,
                episodes,
                routeDiversityBonus,
                deadEndEdgesByMap=deadEndEdgesByMap,
                loopEdgesByMap=loopEdgesByMap,
                bestEdgesByMap=bestEdgesByMap,
                attemptIndex=attemptIndex,
                deterministic=deterministic,
            )
            actions, logProbs, values, entropies, nextState = chooseActionsBatch(
                model,
                obsBatch,
                subState,
                deterministic=deterministic,
                logitBias=logitBias,
                actionMask=maskBatch,
            )
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
                maskBefore = maskBatch[j].tolist()
                nextObs, reward, done, info = envs[i].step(action)
                ep = episodes[i]
                if recordTrajectory:
                    ep["observations"].append(observations[i])
                    ep["actionMasks"].append(maskBefore)
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
        ep["scoreLimitExceeded"] = bool(info.get("scoreLimitExceeded", False))
        ep["failed"] = bool(info.get("failed", not ep["won"]))
        ep["score"] = int(info.get("score", 0))
        ep["officialScore"] = int(info.get("officialScore", ep["score"]))
        ep["trainingScore"] = int(info.get("trainingScore", ep["score"]))
        ep["totalBoneScoreReduction"] = int(info.get("totalBoneScoreReduction", 0))
        ep["bonesCollected"] = int(info.get("bonesCollected", 0))
        ep["totalBones"] = len(env.bones)
        ep["allFiveBonesCollected"] = bool(ep["bonesCollected"] >= 5)
        ep["length"] = len(ep["actions"])
        ep["steps"] = len(ep["actions"])
        ep["revisits"] = int(env.revisits)
        ep["revisitPercentage"] = float(env.revisitPercentage())
        ep["revisitRate"] = float(env.revisits) / float(max(1, len(ep["actions"])))
        ep["wallBumps"] = int(env.wallBumps)
        ep["uniqueCells"] = len(env.visitCounts)
        ep["discoveredCellsCount"] = len(env.discoveredCells)
        ep["newAreasExplored"] = int(env.newAreasExploredCount())
        ep["deadEndsEncountered"] = int(env.deadEndsEncountered)
        ep["deadEndReentries"] = int(env.deadEndReentries)
        ep["oscillationsDetected"] = int(env.oscillationsDetected)
        ep["repeatedMistakes"] = int(env.totalMistakesCount())
        ep["avoidedPreviousMistakes"] = int(env.avoidedPreviousMistakes)
        ep["knownDeadEnds"] = [[int(p[0]), int(p[1])] for p in sorted(env.knownDeadEnds)]
        ep["knownJunctions"] = [[int(p[0]), int(p[1])] for p in sorted(env.knownJunctions)]
        ep["deadEndEdges"] = list(sorted(env.deadEndEdges))
        ep["loopEdges"] = list(sorted(env.loopEdges))
        ep["maxVisitCount"] = int(env.maxVisitCount())
        ep["mostVisitedCell"] = env.mostVisitedCell()
        ep["mostFrequentlyRevisitedCell"] = env.mostFrequentlyRevisitedCell()
        ep["visitedCells"] = [[int(p[0]), int(p[1])] for p in env.visitCounts.keys()]
        ep["collectedBones"] = [[int(p[0]), int(p[1])] for p in env.collectedBonesOrder]
        ep["boneCollectionEvents"] = list(env.boneCollectionEvents)
        ep["positionHistory"] = list(env.positionHistory)
        ep["edgesTraversed"] = [(int(pos[0]), int(pos[1]), int(act)) for (pos, act) in env.edgeCounts.keys()]
        ep["totalReward"] = float(sum(ep["rewards"]))
        ep["rawTotalReward"] = float(sum(ep["rawRewards"]))
        ep["meanEntropy"] = float(np.mean(ep["entropies"])) if ep["entropies"] else 0.0
        env._archiveEpisodeIntoPriorMemory()
        ep["updatedMazeMemory"] = env.priorMazeMemory
    return episodes


def collectEpisode(
    model,
    mazeData,
    maxSteps=300,
    deterministic=False,
    rewardConfig=None,
    enforceScoreLimit=True,
):
    return collectEpisodes(
        model,
        [mazeData],
        maxSteps=maxSteps,
        deterministic=deterministic,
        rewardConfig=rewardConfig,
        enforceScoreLimit=enforceScoreLimit,
    )[0]


def collectRepeatedEpisodes(
    model,
    mazes,
    attemptsPerMaze=2,
    maxSteps=300,
    deterministic=False,
    rewardConfig=None,
    routeDiversityBonus=0.65,
    enforceScoreLimit=True,
    priorEdgesByMap=None,
    deadEndEdgesByMap=None,
    loopEdgesByMap=None,
    bestEdgesByMap=None,
):
    """Run multiple consecutive attempts on each maze without resetting model weights."""
    attempts = max(1, int(attemptsPerMaze))
    edgeMemory = {k: set(v) for k, v in (priorEdgesByMap or {}).items()}
    deadEndMemory = {k: set(v) for k, v in (deadEndEdgesByMap or {}).items()}
    loopMemory = {k: set(v) for k, v in (loopEdgesByMap or {}).items()}
    bestEdgeMemory = {k: set(v) for k, v in (bestEdgesByMap or {}).items()}
    bestScoreByMap = {}
    mazeMemories = {}

    allAttempts = []
    for attemptIdx in range(1, attempts + 1):
        bonus = float(routeDiversityBonus) if attemptIdx > 1 and not deterministic else 0.0
        batchEps = collectEpisodes(
            model,
            mazes,
            maxSteps=maxSteps,
            deterministic=deterministic,
            rewardConfig=rewardConfig,
            recordTrajectory=True,
            enforceScoreLimit=enforceScoreLimit,
            priorEdgesByMap=edgeMemory,
            routeDiversityBonus=bonus,
            attemptIndex=attemptIdx,
            deadEndEdgesByMap=deadEndMemory,
            loopEdgesByMap=loopMemory,
            bestEdgesByMap=bestEdgeMemory,
            priorMazeMemoryByMap=mazeMemories,
        )
        for ep in batchEps:
            mapName = ep["sourceMap"]
            edgeMemory.setdefault(mapName, set()).update(ep.get("edgesTraversed", []))
            deadEndMemory.setdefault(mapName, set()).update(ep.get("deadEndEdges", []))
            loopMemory.setdefault(mapName, set()).update(ep.get("loopEdges", []))
            if "updatedMazeMemory" in ep:
                mazeMemories[mapName] = ep.pop("updatedMazeMemory")
            if ep.get("won") or ep.get("bonesCollected", 0) > 0:
                scoreVal = ep.get("trainingScore", ep.get("score", 999))
                prevBest = bestScoreByMap.get(mapName)
                if prevBest is None or (ep.get("won") and scoreVal < prevBest):
                    if ep.get("won"):
                        bestScoreByMap[mapName] = scoreVal
                    bestEdgeMemory[mapName] = set(ep.get("edgesTraversed", []))
        allAttempts.extend(batchEps)
    return allAttempts

