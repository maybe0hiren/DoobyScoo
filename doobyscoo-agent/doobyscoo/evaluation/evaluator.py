from pathlib import Path
import numpy as np
import torch
from ..training.rollout import collectEpisodes
from ..environment.maze_environment import loadMaze


def evaluate(model, paths, episodesPerMap=1, maxSteps=300, deterministic=True, modelVersion=1, rewardConfig=None):
    """Evaluate `model` across `paths`. Uses deterministic policy selection by default
    for reproducible comparisons across training stages."""
    pathItems = list(paths)
    if not pathItems:
        return {
            "winRate": 0.0,
            "failureRate": 1.0,
            "timeoutRate": 0.0,
            "meanScore": 0.0,
            "medianScore": 0.0,
            "meanSteps": 0.0,
            "meanEpisodeLength": 0.0,
            "bonesCollected": 0.0,
            "meanBonesCollected": 0.0,
            "boneCollectionRate": 0.0,
            "meanRevisits": 0.0,
            "revisitRate": 0.0,
            "meanUniqueSquares": 0.0,
            "meanWallBumps": 0.0,
            "meanReward": 0.0,
            "episodes": 0,
            "modelVersion": int(modelVersion),
            "resultsPerMap": {},
        }

    expandedMazes = []
    expandedNames = []
    for idx, item in enumerate(pathItems):
        if isinstance(item, dict):
            mazeData = item
            mapName = mazeData.get("metadata", {}).get("maze_name", f"map_{idx}")
        else:
            pathObj = Path(item)
            mazeData = loadMaze(pathObj)
            mapName = pathObj.name
        for _ in range(int(episodesPerMap)):
            expandedMazes.append(mazeData)
            expandedNames.append(mapName)

    wasTraining = model.training
    model.eval()
    with torch.no_grad():
        episodes = collectEpisodes(
            model,
            expandedMazes,
            maxSteps=maxSteps,
            deterministic=deterministic,
            rewardConfig=rewardConfig,
            recordTrajectory=False,
        )
    if wasTraining:
        model.train()

    wins = [1.0 if ep["won"] else 0.0 for ep in episodes]
    timeouts = [1.0 if ep["timeout"] else 0.0 for ep in episodes]
    scores = [ep["score"] for ep in episodes]
    lengths = [ep["length"] for ep in episodes]
    bonesList = [ep["bonesCollected"] for ep in episodes]
    totalBonesList = [ep["totalBones"] for ep in episodes]
    revisitsList = [ep["revisits"] for ep in episodes]
    revisitRates = [ep["revisits"] / float(max(1, ep["length"])) for ep in episodes]
    uniqueList = [ep["uniqueCells"] for ep in episodes]
    wallBumpsList = [ep["wallBumps"] for ep in episodes]
    rewards = [ep["totalReward"] for ep in episodes]

    grouped = {}
    for mapName, ep in zip(expandedNames, episodes):
        grouped.setdefault(mapName, []).append(ep)

    resultsPerMap = {}
    for mapName, mapEps in grouped.items():
        mWins = [1.0 if e["won"] else 0.0 for e in mapEps]
        mScores = [e["score"] for e in mapEps]
        mSteps = [e["length"] for e in mapEps]
        mBones = [e["bonesCollected"] for e in mapEps]
        mTotalBones = [e["totalBones"] for e in mapEps]
        mRevisits = [e["revisits"] for e in mapEps]
        mRevRates = [e["revisits"] / float(max(1, e["length"])) for e in mapEps]
        mUnique = [e["uniqueCells"] for e in mapEps]
        resultsPerMap[mapName] = {
            "winRate": float(np.mean(mWins)),
            "meanScore": float(np.mean(mScores)),
            "meanSteps": float(np.mean(mSteps)),
            "meanBones": float(np.mean(mBones)),
            "boneCollectionRate": float(sum(mBones)) / float(max(1, sum(mTotalBones))),
            "meanRevisits": float(np.mean(mRevisits)),
            "revisitRate": float(np.mean(mRevRates)),
            "meanUniqueSquares": float(np.mean(mUnique)),
            "won": bool(all(e["won"] for e in mapEps)),
        }

    winRate = float(np.mean(wins))
    timeoutRate = float(np.mean(timeouts))
    boneRate = float(sum(bonesList)) / float(max(1, sum(totalBonesList)))
    return {
        "winRate": winRate,
        "failureRate": float(1.0 - winRate),
        "timeoutRate": timeoutRate,
        "meanScore": float(np.mean(scores)),
        "medianScore": float(np.median(scores)),
        "meanSteps": float(np.mean(lengths)),
        "meanEpisodeLength": float(np.mean(lengths)),
        "bonesCollected": float(np.mean(bonesList)),
        "meanBonesCollected": float(np.mean(bonesList)),
        "boneCollectionRate": boneRate,
        "meanRevisits": float(np.mean(revisitsList)),
        "revisitRate": float(np.mean(revisitRates)),
        "meanUniqueSquares": float(np.mean(uniqueList)),
        "meanWallBumps": float(np.mean(wallBumpsList)),
        "meanReward": float(np.mean(rewards)),
        "episodes": len(episodes),
        "modelVersion": int(modelVersion),
        "resultsPerMap": resultsPerMap,
    }
