import json
import random
from pathlib import Path
import numpy as np
import torch
from ..agent.network import RecurrentPolicy
from ..agent.ppo import updatePolicy
from ..config import entropyCoefficient, makeConfig, rewardConfigForUpdate
from ..training.curriculum import BalancedMapSampler
from ..training.rehearsal import RehearsalManager
from ..training.rollout import collectEpisodes, discoverMaps, gridHash
from ..environment.maze_environment import loadMaze
from .evaluator import evaluate


def _delta(before, after):
    return {
        "winRateDelta": float(after["winRate"] - before["winRate"]),
        "meanScoreDelta": float(after["meanScore"] - before["meanScore"]),
        "meanStepsDelta": float(after["meanSteps"] - before["meanSteps"]),
        "bonesCollectedDelta": float(after["bonesCollected"] - before["bonesCollected"]),
        "boneCollectionRateDelta": float(after["boneCollectionRate"] - before["boneCollectionRate"]),
        "meanRevisitsDelta": float(after["meanRevisits"] - before["meanRevisits"]),
        "revisitRateDelta": float(after["revisitRate"] - before["revisitRate"]),
    }


def _trainStage(model, optimizer, activePaths, cfg, updates, rehearsalManager=None, startUpdate=0,
                evalTargetPaths=None, targetWinRate=0.80):
    episodesPerUpdate = int(cfg["training"]["episodesPerUpdate"])
    maxSteps = int(cfg["training"]["maxSteps"])
    rehearsalProb = float(cfg["rehearsal"]["probability"]) if rehearsalManager is not None else 0.0
    sampler = BalancedMapSampler(
        activePaths,
        struggleFraction=cfg["sampling"]["struggleFraction"],
        uniqueMapsPerBatch=cfg["sampling"]["uniqueMapsPerBatch"],
    )
    ppoCfg = cfg["ppo"]
    episodesToTarget = None
    updatesToTarget = None
    totalNewEpisodes = 0
    curve = []

    for idx in range(1, int(updates) + 1):
        updNum = startUpdate + idx
        rc = rewardConfigForUpdate(cfg, updNum)
        rehCount = int(round(episodesPerUpdate * rehearsalProb)) if rehearsalManager is not None else 0
        newCount = max(1, episodesPerUpdate - rehCount)
        sampledNew = sampler.sample(count=newCount)
        if not isinstance(sampledNew, list):
            sampledNew = [sampledNew]
        newEps = collectEpisodes(model, sampledNew, maxSteps=maxSteps, deterministic=False, rewardConfig=rc)
        for p, ep in zip(sampledNew, newEps):
            sampler.recordOutcome(p, ep["won"], ep["score"])
        rehEps = (
            rehearsalManager.generateRehearsalEpisodes(
                model,
                count=rehCount,
                maxSteps=maxSteps,
                rewardConfig=rc,
                playedRatio=cfg["rehearsal"].get("playedRatio", 0.0),
            )
            if rehCount > 0 and rehearsalManager is not None
            else []
        )
        batch = newEps + rehEps
        totalNewEpisodes += len(newEps)
        entCoef = entropyCoefficient(cfg, updNum)
        updatePolicy(
            model,
            optimizer,
            batch,
            epochs=ppoCfg["epochs"],
            clipRange=ppoCfg["clipRange"],
            valueCoef=ppoCfg["valueCoef"],
            entropyCoef=entCoef,
            maxGradNorm=ppoCfg["maxGradNorm"],
            gamma=ppoCfg["gamma"],
            gaeLambda=ppoCfg["gaeLambda"],
            shortGamma=ppoCfg.get("shortGamma", 0.50),
            shortLambda=ppoCfg.get("shortLambda", 0.50),
            shortAdvantageWeight=ppoCfg.get("shortAdvantageWeight", 0.55),
            minibatchEpisodes=ppoCfg["minibatchEpisodes"],
            targetKl=ppoCfg["targetKl"],
        )
        if evalTargetPaths is not None and (idx == 1 or idx % 2 == 0 or idx == updates):
            ev = evaluate(model, evalTargetPaths, maxSteps=maxSteps, deterministic=True)
            curve.append({
                "update": idx,
                "episodesOnNewMaps": totalNewEpisodes,
                "winRate": ev["winRate"],
                "meanScore": ev["meanScore"],
                "bonesCollected": ev["bonesCollected"],
                "boneCollectionRate": ev["boneCollectionRate"],
                "revisitRate": ev["revisitRate"],
            })
            if episodesToTarget is None and ev["winRate"] >= targetWinRate:
                episodesToTarget = totalNewEpisodes
                updatesToTarget = idx

    return {
        "episodesToTarget": episodesToTarget,
        "updatesToTarget": updatesToTarget,
        "totalNewEpisodes": totalNewEpisodes,
        "learningCurve": curve,
    }


def runKnowledgeTransferEvaluation(
    trainMapsFolder="maps/train",
    testMapsFolder="maps/test",
    phase1Updates=25,
    phase2Updates=20,
    config=None,
    seed=42,
    reportPath=None,
):
    """Run the 5-phase knowledge-transfer and retention experiment on three isolated map groups.

    1. Initial training maps (first half of trainMapsFolder, stratified across difficulties).
    2. Newly introduced training maps (second half of trainMapsFolder).
    3. Completely unseen test maps (testMapsFolder — never enters training or rehearsal).
    """
    cfg = makeConfig(config)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    allTrain = discoverMaps(trainMapsFolder, excludedFolders=[testMapsFolder])
    testPaths = discoverMaps(testMapsFolder)
    testHashes = {gridHash(loadMaze(p)) for p in testPaths}
    for p in allTrain:
        if gridHash(loadMaze(p)) in testHashes:
            raise ValueError(f"Test map leaked into training pool: {p}")

    initialMaps = [p for i, p in enumerate(allTrain) if i % 2 == 0]
    newMaps = [p for i, p in enumerate(allTrain) if i % 2 == 1]
    maxSteps = int(cfg["training"]["maxSteps"])

    model = RecurrentPolicy(hiddenSize=cfg["ppo"]["hiddenSize"])
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["ppo"]["learningRate"])

    # Phase 0: Untrained baseline across all three map groups
    untrainedInitial = evaluate(model, initialMaps, maxSteps=maxSteps, deterministic=True, modelVersion=0)
    untrainedNew = evaluate(model, newMaps, maxSteps=maxSteps, deterministic=True, modelVersion=0)
    untrainedTest = evaluate(model, testPaths, maxSteps=maxSteps, deterministic=True, modelVersion=0)

    # Phase 1: Train fresh model on initialMaps only
    phase1TrainInfo = _trainStage(
        model,
        optimizer,
        initialMaps,
        cfg,
        updates=phase1Updates,
        rehearsalManager=None,
        startUpdate=0,
        evalTargetPaths=initialMaps,
    )
    phase1Initial = evaluate(model, initialMaps, maxSteps=maxSteps, deterministic=True, modelVersion=1)
    phase1NewZeroShot = evaluate(model, newMaps, maxSteps=maxSteps, deterministic=True, modelVersion=1)
    phase1Test = evaluate(model, testPaths, maxSteps=maxSteps, deterministic=True, modelVersion=1)

    # Phase 2: Introduce newMaps while rehearsing initialMaps on the SAME model & optimizer
    rehearsal = RehearsalManager(
        trainMapsFolder=None,
        playedMapsFolder=None,
        excludedFolders=[testMapsFolder],
        extraMaps=initialMaps,
        excludedHashes=testHashes,
    )
    phase2TransferInfo = _trainStage(
        model,
        optimizer,
        newMaps,
        cfg,
        updates=phase2Updates,
        rehearsalManager=rehearsal,
        startUpdate=phase1Updates,
        evalTargetPaths=newMaps,
    )

    # Control: how many episodes does a scratch model (no Phase 1 prior) need on newMaps?
    random.seed(seed + 100)
    np.random.seed(seed + 100)
    torch.manual_seed(seed + 100)
    scratchModel = RecurrentPolicy(hiddenSize=cfg["ppo"]["hiddenSize"])
    scratchOptimizer = torch.optim.Adam(scratchModel.parameters(), lr=cfg["ppo"]["learningRate"])
    scratchOnNewInfo = _trainStage(
        scratchModel,
        scratchOptimizer,
        newMaps,
        cfg,
        updates=phase2Updates,
        rehearsalManager=None,
        startUpdate=0,
        evalTargetPaths=newMaps,
    )

    # Phase 3: Knowledge retention on initialMaps after Phase 2
    phase3RetentionInitial = evaluate(model, initialMaps, maxSteps=maxSteps, deterministic=True, modelVersion=2)
    # Phase 4: Knowledge transfer on newMaps after Phase 2
    phase4TransferNew = evaluate(model, newMaps, maxSteps=maxSteps, deterministic=True, modelVersion=2)
    # Phase 5: Generalization on completely unseen testMaps
    phase5GeneralizationTest = evaluate(model, testPaths, maxSteps=maxSteps, deterministic=True, modelVersion=2)

    retentionDelta = _delta(phase1Initial, phase3RetentionInitial)
    zeroShotTransferDelta = _delta(untrainedNew, phase1NewZeroShot)
    postTrainTransferDelta = _delta(untrainedNew, phase4TransferNew)
    generalizationDelta = _delta(untrainedTest, phase5GeneralizationTest)

    catastrophicForgetting = retentionDelta["winRateDelta"] < -0.15
    knowledgeTransferred = (
        phase1NewZeroShot["winRate"] > untrainedNew["winRate"]
        and phase4TransferNew["winRate"] >= 0.85
        and phase5GeneralizationTest["winRate"] >= 0.85
    )

    report = {
        "mapGroups": {
            "initialTrainingMapsCount": len(initialMaps),
            "newlyIntroducedMapsCount": len(newMaps),
            "unseenTestMapsCount": len(testPaths),
            "initialTrainingMaps": [p.name for p in initialMaps],
            "newlyIntroducedMaps": [p.name for p in newMaps],
            "unseenTestMaps": [p.name for p in testPaths],
            "testMapsIsolated": True,
        },
        "phase0_untrainedBaseline": {
            "initialMaps": untrainedInitial,
            "newMaps": untrainedNew,
            "unseenTestMaps": untrainedTest,
        },
        "phase1_initialLearning": {
            "updates": int(phase1Updates),
            "trainingProgress": phase1TrainInfo,
            "initialMaps": phase1Initial,
            "newMapsZeroShot": phase1NewZeroShot,
            "unseenTestMaps": phase1Test,
        },
        "phase2_newMapsWithRehearsal": {
            "updates": int(phase2Updates),
            "transferProgress": phase2TransferInfo,
            "scratchBaselineProgress": scratchOnNewInfo,
        },
        "phase3_knowledgeRetention": {
            "initialMapsBeforeNewTraining": phase1Initial,
            "initialMapsAfterNewTraining": phase3RetentionInitial,
            "delta": retentionDelta,
            "catastrophicForgettingDetected": bool(catastrophicForgetting),
        },
        "phase4_knowledgeTransfer": {
            "newMapsUntrained": untrainedNew,
            "newMapsZeroShotAfterPhase1": phase1NewZeroShot,
            "newMapsAfterPhase2": phase4TransferNew,
            "zeroShotDelta": zeroShotTransferDelta,
            "postTrainingDelta": postTrainTransferDelta,
            "episodesTo80PctWinWithTransfer": phase2TransferInfo["episodesToTarget"],
            "episodesTo80PctWinFromScratch": scratchOnNewInfo["episodesToTarget"],
        },
        "phase5_unseenGeneralization": {
            "unseenUntrained": untrainedTest,
            "unseenAfterPhase1": phase1Test,
            "unseenAfterPhase2": phase5GeneralizationTest,
            "deltaFromUntrained": generalizationDelta,
        },
        "verdict": {
            "catastrophicForgettingDetected": bool(catastrophicForgetting),
            "knowledgeTransferVerified": bool(knowledgeTransferred),
            "retentionWinRate": float(phase3RetentionInitial["winRate"]),
            "zeroShotNewMapsWinRate": float(phase1NewZeroShot["winRate"]),
            "trainedNewMapsWinRate": float(phase4TransferNew["winRate"]),
            "unseenTestWinRate": float(phase5GeneralizationTest["winRate"]),
            "unseenTestBoneCollectionRate": float(phase5GeneralizationTest["boneCollectionRate"]),
            "unseenTestRevisitRate": float(phase5GeneralizationTest["revisitRate"]),
        },
    }

    if reportPath is not None:
        rp = Path(reportPath)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return report, model

