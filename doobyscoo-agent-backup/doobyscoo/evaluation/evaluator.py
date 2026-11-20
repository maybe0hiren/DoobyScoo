from pathlib import Path
import numpy as np
import torch
from ..environment.maze_environment import loadMaze


def evaluate(
    model,
    paths,
    episodesPerMap=1,
    maxSteps=300,
    deterministic=True,
    modelVersion=1,
    rewardConfig=None,
    enforceScoreLimit=True,
):
    """Evaluate `model` across `paths`. Uses deterministic policy selection by default
    for reproducible comparisons across training stages; when `episodesPerMap > 1` and
    `deterministic=False`, runs repeated exploratory attempts to measure multi-attempt
    route diversity, mistake reduction, and score improvement."""
    from ..training.metrics import MazeOptimizationTracker
    from ..training.rollout import collectEpisodes, collectRepeatedEpisodes

    pathItems = list(paths)
    if not pathItems:
        return {
            "winRate": 0.0,
            "failureRate": 1.0,
            "timeoutRate": 0.0,
            "scoreLimitFailureRate": 0.0,
            "meanScore": 0.0,
            "medianScore": 0.0,
            "meanTrainingScore": 0.0,
            "medianTrainingScore": 0.0,
            "meanSteps": 0.0,
            "meanEpisodeLength": 0.0,
            "bonesCollected": 0.0,
            "meanBonesCollected": 0.0,
            "boneCollectionRate": 0.0,
            "fiveBoneCompletionRate": 0.0,
            "meanRevisits": 0.0,
            "revisitRate": 0.0,
            "revisitPercentage": 0.0,
            "meanUniqueSquares": 0.0,
            "meanNewAreasExplored": 0.0,
            "totalNewAreasExplored": 0,
            "meanDeadEndsEncountered": 0.0,
            "totalDeadEndsEncountered": 0,
            "meanRepeatedMistakes": 0.0,
            "totalRepeatedMistakes": 0,
            "totalAvoidedMistakes": 0,
            "maxVisitCount": 0,
            "meanWallBumps": 0.0,
            "meanReward": 0.0,
            "averageAttemptsBeforeImprovement": 0.0,
            "distinctSuccessfulTrajectories": 0,
            "distinctRoutes": 0,
            "scoreImprovementAcrossAttempts": 0.0,
            "episodes": 0,
            "modelVersion": int(modelVersion),
            "resultsPerMap": {},
        }

    baseMazes = []
    baseNames = []
    for idx, item in enumerate(pathItems):
        if isinstance(item, dict):
            mazeData = item
            mapName = mazeData.get("metadata", {}).get("maze_name", f"map_{idx}")
        else:
            pathObj = Path(item)
            mazeData = loadMaze(pathObj)
            mapName = pathObj.name
        baseMazes.append(mazeData)
        baseNames.append(mapName)

    wasTraining = model.training
    model.eval()
    with torch.no_grad():
        if int(episodesPerMap) > 1:
            episodes = collectRepeatedEpisodes(
                model,
                pathItems,
                attemptsPerMaze=int(episodesPerMap),
                maxSteps=maxSteps,
                deterministic=deterministic,
                rewardConfig=rewardConfig,
                routeDiversityBonus=0.55 if not deterministic else 0.0,
                enforceScoreLimit=enforceScoreLimit,
            )
        else:
            episodes = collectEpisodes(
                model,
                baseMazes,
                maxSteps=maxSteps,
                deterministic=deterministic,
                rewardConfig=rewardConfig,
                recordTrajectory=False,
                enforceScoreLimit=enforceScoreLimit,
            )
            for ep, mName in zip(episodes, baseNames):
                ep["sourceMap"] = mName
    if wasTraining:
        model.train()

    optTracker = MazeOptimizationTracker()
    for ep in episodes:
        optTracker.recordAttempt(ep["sourceMap"], ep)

    wins = [1.0 if ep["won"] else 0.0 for ep in episodes]
    timeouts = [1.0 if ep["timeout"] else 0.0 for ep in episodes]
    scoreLimitFails = [1.0 if ep.get("scoreLimitExceeded", False) else 0.0 for ep in episodes]
    scores = [ep["score"] for ep in episodes]
    trainingScores = [ep.get("trainingScore", ep["score"]) for ep in episodes]
    lengths = [ep["length"] for ep in episodes]
    bonesList = [ep["bonesCollected"] for ep in episodes]
    fiveBoneList = [1.0 if ep["bonesCollected"] >= 5 else 0.0 for ep in episodes]
    totalBonesList = [ep["totalBones"] for ep in episodes]
    revisitsList = [ep["revisits"] for ep in episodes]
    revisitRates = [ep["revisits"] / float(max(1, ep["length"])) for ep in episodes]
    uniqueList = [ep["uniqueCells"] for ep in episodes]
    newAreasList = [ep.get("newAreasExplored", ep["uniqueCells"]) for ep in episodes]
    deadEndsList = [ep.get("deadEndsEncountered", 0) for ep in episodes]
    mistakesList = [ep.get("repeatedMistakes", 0) for ep in episodes]
    avoidedList = [ep.get("avoidedPreviousMistakes", 0) for ep in episodes]
    maxVisitList = [ep.get("maxVisitCount", 1) for ep in episodes]
    wallBumpsList = [ep["wallBumps"] for ep in episodes]
    rewards = [ep["totalReward"] for ep in episodes]

    grouped = {}
    for ep in episodes:
        grouped.setdefault(ep["sourceMap"], []).append(ep)

    resultsPerMap = {}
    for mapName, mapEps in grouped.items():
        mWins = [1.0 if e["won"] else 0.0 for e in mapEps]
        mScores = [e["score"] for e in mapEps]
        mTrainScores = [e.get("trainingScore", e["score"]) for e in mapEps]
        mSteps = [e["length"] for e in mapEps]
        mBones = [e["bonesCollected"] for e in mapEps]
        mFiveBones = [1.0 if e["bonesCollected"] >= 5 else 0.0 for e in mapEps]
        mTotalBones = [e["totalBones"] for e in mapEps]
        mRevisits = [e["revisits"] for e in mapEps]
        mRevRates = [e["revisits"] / float(max(1, e["length"])) for e in mapEps]
        mUnique = [e["uniqueCells"] for e in mapEps]
        mDeadEnds = [e.get("deadEndsEncountered", 0) for e in mapEps]
        mMistakes = [e.get("repeatedMistakes", 0) for e in mapEps]
        mNewAreas = [e.get("newAreasExplored", e["uniqueCells"]) for e in mapEps]
        mSummary = optTracker.getMazeSummary(mapName) or {}
        resultsPerMap[mapName] = {
            "winRate": float(np.mean(mWins)),
            "meanScore": float(np.mean(mScores)),
            "bestScore": mSummary.get("bestOfficialScore", float(np.min(mScores))),
            "meanTrainingScore": float(np.mean(mTrainScores)),
            "bestTrainingScore": mSummary.get("bestTrainingScore", float(np.min(mTrainScores))),
            "meanSteps": float(np.mean(mSteps)),
            "bestSteps": mSummary.get("bestSteps", int(np.min(mSteps))),
            "meanBones": float(np.mean(mBones)),
            "maxBones": mSummary.get("maxBonesCollected", int(np.max(mBones))),
            "boneCollectionRate": float(sum(mBones)) / float(max(1, sum(mTotalBones))),
            "fiveBoneCompletionRate": float(np.mean(mFiveBones)),
            "meanRevisits": float(np.mean(mRevisits)),
            "revisitRate": float(np.mean(mRevRates)),
            "revisitPercentage": float(100.0 * np.mean(mRevRates)),
            "meanUniqueSquares": float(np.mean(mUnique)),
            "meanDeadEndsEncountered": float(np.mean(mDeadEnds)),
            "totalDeadEndsEncountered": int(sum(mDeadEnds)),
            "meanRepeatedMistakes": float(np.mean(mMistakes)),
            "totalRepeatedMistakes": int(sum(mMistakes)),
            "meanNewAreasExplored": float(np.mean(mNewAreas)),
            "totalNewAreasExplored": int(mSummary.get("totalNewAreasExplored", sum(mNewAreas))),
            "distinctRoutes": int(mSummary.get("distinctRoutes", 0)),
            "distinctSuccessfulTrajectories": int(mSummary.get("distinctSuccessfulTrajectories", 0)),
            "scoreImprovement": int(mSummary.get("scoreImprovement", 0)),
            "averageAttemptsBeforeImprovement": float(mSummary.get("averageAttemptsBeforeImprovement", 0.0)),
            "won": bool(any(e["won"] for e in mapEps)),
        }

    globalOpt = optTracker.globalSummary()
    winRate = float(np.mean(wins))
    timeoutRate = float(np.mean(timeouts))
    boneRate = float(sum(bonesList)) / float(max(1, sum(totalBonesList)))
    revRateMean = float(np.mean(revisitRates))
    return {
        "winRate": winRate,
        "failureRate": float(1.0 - winRate),
        "timeoutRate": timeoutRate,
        "scoreLimitFailureRate": float(np.mean(scoreLimitFails)),
        "meanScore": float(np.mean(scores)),
        "medianScore": float(np.median(scores)),
        "meanTrainingScore": float(np.mean(trainingScores)),
        "medianTrainingScore": float(np.median(trainingScores)),
        "meanSteps": float(np.mean(lengths)),
        "meanEpisodeLength": float(np.mean(lengths)),
        "bonesCollected": float(np.mean(bonesList)),
        "meanBonesCollected": float(np.mean(bonesList)),
        "boneCollectionRate": boneRate,
        "fiveBoneCompletionRate": float(np.mean(fiveBoneList)),
        "meanRevisits": float(np.mean(revisitsList)),
        "revisitRate": revRateMean,
        "revisitPercentage": float(100.0 * revRateMean),
        "meanUniqueSquares": float(np.mean(uniqueList)),
        "meanNewAreasExplored": float(np.mean(newAreasList)),
        "totalNewAreasExplored": int(globalOpt.get("totalNewAreasExplored", sum(newAreasList))),
        "meanDeadEndsEncountered": float(np.mean(deadEndsList)),
        "totalDeadEndsEncountered": int(sum(deadEndsList)),
        "meanRepeatedMistakes": float(np.mean(mistakesList)),
        "totalRepeatedMistakes": int(sum(mistakesList)),
        "totalAvoidedMistakes": int(sum(avoidedList)),
        "maxVisitCount": int(max(maxVisitList)) if maxVisitList else 0,
        "meanWallBumps": float(np.mean(wallBumpsList)),
        "meanReward": float(np.mean(rewards)),
        "averageAttemptsBeforeImprovement": float(globalOpt.get("averageAttemptsBeforeImprovement", 0.0)),
        "distinctSuccessfulTrajectories": int(globalOpt.get("distinctSuccessfulTrajectories", 0)),
        "distinctRoutes": int(globalOpt.get("distinctRoutes", 0)),
        "scoreImprovementAcrossAttempts": float(globalOpt.get("meanScoreImprovement", 0.0)),
        "episodes": len(episodes),
        "modelVersion": int(modelVersion),
        "resultsPerMap": resultsPerMap,
    }
