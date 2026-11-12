import json
import random
import uuid
from pathlib import Path
import numpy as np
import torch
from ..agent.network import RecurrentPolicy
from ..agent.ppo import updatePolicy
from ..config import entropyCoefficient, makeConfig, rewardConfigForUpdate
from ..evaluation.evaluator import evaluate
from ..storage.checkpoint import (
    IncompatibleCheckpointError,
    bestCheckpointPath,
    loadCheckpointFull,
    metricsLogPath,
    saveCheckpoint,
)
from .curriculum import BalancedMapSampler
from .metrics import TrainingMetricsTracker
from .rehearsal import RehearsalManager
from .rollout import collectEpisodes, discoverMaps


def _updateMapHistory(mapHistory, episodes):
    for ep in episodes:
        name = str(ep.get("sourceMap", "unknown"))
        entry = mapHistory.get(
            name,
            {
                "plays": 0,
                "wins": 0,
                "winRate": 0.0,
                "meanScore": 0.0,
                "meanBones": 0.0,
                "meanRevisits": 0.0,
            },
        )
        plays = int(entry["plays"]) + 1
        wins = int(entry["wins"]) + (1 if ep.get("won") else 0)
        alpha = 1.0 / min(plays, 10)
        entry["plays"] = plays
        entry["wins"] = wins
        entry["winRate"] = round(wins / float(plays), 4)
        entry["meanScore"] = round((1.0 - alpha) * float(entry["meanScore"]) + alpha * float(ep.get("score", 0)), 3)
        entry["meanBones"] = round((1.0 - alpha) * float(entry["meanBones"]) + alpha * float(ep.get("bonesCollected", 0)), 3)
        entry["meanRevisits"] = round((1.0 - alpha) * float(entry["meanRevisits"]) + alpha * float(ep.get("revisits", 0)), 3)
        mapHistory[name] = entry


def _removeStaleCheckpointFiles(checkpointPath):
    ckpt = Path(checkpointPath)
    for candidate in (
        ckpt,
        ckpt.with_suffix(ckpt.suffix + ".bak"),
        ckpt.with_suffix(ckpt.suffix + ".tmp"),
        bestCheckpointPath(ckpt),
        bestCheckpointPath(ckpt).with_suffix(ckpt.suffix + ".bak"),
        metricsLogPath(ckpt),
    ):
        if candidate.exists():
            try:
                candidate.unlink()
            except OSError:
                pass


def train(
    mapsFolder,
    checkpoint="models/dog.pt",
    updates=100,
    episodesPerUpdate=None,
    maxSteps=None,
    learningRate=None,
    rehearsalFolder=None,
    validationFolder=None,
    resume=True,
    cpuThreads=None,
    config=None,
    seed=None,
):
    cfg = makeConfig(config)
    if episodesPerUpdate is not None:
        cfg["training"]["episodesPerUpdate"] = int(episodesPerUpdate)
    if maxSteps is not None:
        cfg["training"]["maxSteps"] = int(maxSteps)
    if learningRate is not None:
        cfg["ppo"]["learningRate"] = float(learningRate)
    if cpuThreads is not None:
        cfg["training"]["cpuThreads"] = int(cpuThreads)
    if seed is not None:
        cfg["training"]["seed"] = int(seed)

    episodesPerUpdate = int(cfg["training"]["episodesPerUpdate"])
    maxSteps = int(cfg["training"]["maxSteps"])
    learningRate = float(cfg["ppo"]["learningRate"])
    threads = int(cfg["training"].get("cpuThreads", 4) or 4)
    if threads > 0:
        torch.set_num_threads(min(threads, max(1, torch.get_num_threads())))

    activeSeed = cfg["training"].get("seed")
    if activeSeed is not None:
        random.seed(int(activeSeed))
        np.random.seed(int(activeSeed))
        torch.manual_seed(int(activeSeed))

    excluded = ["maps/test"]
    if validationFolder:
        excluded.append(validationFolder)

    paths = discoverMaps(mapsFolder, excludedFolders=excluded)
    rehearsalManager = None
    if rehearsalFolder and Path(rehearsalFolder).exists():
        rehearsalManager = RehearsalManager(
            trainMapsFolder=rehearsalFolder,
            playedMapsFolder=None,
            excludedFolders=excluded,
        )

    valPaths = []
    if validationFolder and Path(validationFolder).exists():
        try:
            valPaths = discoverMaps(validationFolder, excludedFolders=["maps/test"])
        except ValueError:
            valPaths = []
    if not valPaths:
        valPaths = paths

    checkpointPath = Path(checkpoint)
    model = RecurrentPolicy(hiddenSize=cfg["ppo"]["hiddenSize"])
    optimizer = torch.optim.Adam(model.parameters(), lr=learningRate)

    loadedExisting = False
    if not resume:
        _removeStaleCheckpointFiles(checkpointPath)
    elif checkpointPath.exists():
        try:
            meta = loadCheckpointFull(checkpointPath, model, optimizer=optimizer, restoreRng=False)
            loadedExisting = bool(meta.get("loaded", False))
        except IncompatibleCheckpointError as err:
            print(f"[FRESH INIT] Replacing incompatible checkpoint ({err})", flush=True)
            _removeStaleCheckpointFiles(checkpointPath)
            loadedExisting = False

    if loadedExisting:
        startUpdate = int(meta["updates"])
        bestRate = float(meta["bestRate"])
        bestScore = meta.get("bestScore", None)
        totalEpisodes = int(meta["totalEpisodes"])
        totalSteps = int(meta["totalSteps"])
        version = int(meta["version"])
        modelId = meta.get("modelId") or uuid.uuid4().hex[:12]
        mapHistory = dict(meta.get("mapHistory") or {})
        metricsHistory = list(meta.get("metricsHistory") or [])
        freshInit = meta.get("freshInit")
        print(
            f"[RESUME] Maps: {len(paths)} | ModelId: {modelId} | Resuming from update: {startUpdate} | "
            f"Episodes: {totalEpisodes} | Device: CPU",
            flush=True,
        )
    else:
        startUpdate = 0
        bestRate = 0.0
        bestScore = None
        totalEpisodes = 0
        totalSteps = 0
        version = 0
        modelId = uuid.uuid4().hex[:12]
        mapHistory = {}
        metricsHistory = []
        freshInit = {
            "modelId": modelId,
            "architecture": model.architecture,
            "seed": activeSeed,
            "startedFromScratch": True,
        }
        print(
            f"[FRESH INIT] Starting from a brand-new randomly initialized model "
            f"(modelId={modelId}, arch={model.architecture}) | Maps: {len(paths)} | "
            f"Resuming from update: 0 | Episodes: 0 | Device: CPU",
            flush=True,
        )

    sampler = BalancedMapSampler(
        paths,
        struggleFraction=cfg["sampling"]["struggleFraction"],
        uniqueMapsPerBatch=cfg["sampling"]["uniqueMapsPerBatch"],
    )
    tracker = TrainingMetricsTracker()
    tracker.history = list(metricsHistory)
    bestStateDict = {k: v.detach().clone() for k, v in model.state_dict().items()}
    bestOptimizationState = copy.deepcopy(optimizer.state_dict()) if hasattr(optimizer, "state_dict") else None
    bestPath = bestCheckpointPath(checkpointPath)
    logPath = metricsLogPath(checkpointPath)

    evalStride = 5 if int(updates) >= 5 else max(1, int(updates) // 2)
    ppoCfg = cfg["ppo"]
    rehearsalProb = float(cfg["rehearsal"]["probability"]) if rehearsalManager is not None else 0.0
    lastEvalWin = 0.0
    lastEvalScore = None
    measuredEntropy = None

    for updateIndex in range(1, int(updates) + 1):
        updateNumber = startUpdate + updateIndex
        rc = rewardConfigForUpdate(cfg, updateNumber)

        rehCount = int(round(episodesPerUpdate * rehearsalProb)) if rehearsalManager is not None else 0
        newCount = max(1, episodesPerUpdate - rehCount)
        sampledPaths = sampler.sample(count=newCount)
        if not isinstance(sampledPaths, list):
            sampledPaths = [sampledPaths]

        episodes = collectEpisodes(model, sampledPaths, maxSteps=maxSteps, deterministic=False, rewardConfig=rc)
        for mapPath, ep in zip(sampledPaths, episodes):
            sampler.recordOutcome(mapPath, ep["won"], ep["score"])

        rehEpisodes = []
        if rehCount > 0 and rehearsalManager is not None:
            rehEpisodes = rehearsalManager.generateRehearsalEpisodes(
                model,
                count=rehCount,
                maxSteps=maxSteps,
                rewardConfig=rc,
                playedRatio=cfg["rehearsal"].get("playedRatio", 0.0),
            )
            episodes.extend(rehEpisodes)

        for ep in episodes:
            totalEpisodes += 1
            totalSteps += ep["length"]
        _updateMapHistory(mapHistory, episodes)

        entCoef = entropyCoefficient(cfg, updateNumber, measuredEntropy=measuredEntropy)
        lossMetrics = updatePolicy(
            model,
            optimizer,
            episodes,
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
        measuredEntropy = float(lossMetrics.entropy)

        evalMetrics = None
        checkpointSaved = False
        bestSaved = False
        if updateIndex % evalStride == 0 or updateIndex == int(updates):
            evalMetrics = evaluate(
                model,
                valPaths,
                episodesPerMap=int(cfg["training"].get("evalEpisodesPerMap", 1)),
                maxSteps=maxSteps,
                deterministic=True,
                modelVersion=version + 1,
                rewardConfig=rc,
            )
            evalWin = evalMetrics["winRate"]
            evalScore = evalMetrics["meanScore"]
            lastEvalWin = evalWin
            lastEvalScore = evalScore
            if evalWin > bestRate or (evalWin == bestRate and (bestScore is None or evalScore <= bestScore)):
                bestRate = evalWin
                bestScore = evalScore
                bestStateDict = {k: v.detach().clone() for k, v in model.state_dict().items()}
                bestOptimizationState = copy.deepcopy(optimizer.state_dict())
                bestSaved = True

            version += 1
            checkpointSaved = True

        record = tracker.summarizeBatch(
            updateNumber=updateNumber,
            numMaps=len(paths),
            totalEpisodes=totalEpisodes,
            episodes=episodes,
            updateMetrics=lossMetrics,
            evalMetrics=evalMetrics,
            checkpointSaved=checkpointSaved,
            bestCheckpointSaved=bestSaved,
            entropyCoef=entCoef,
            rehearsalEpisodes=len(rehEpisodes),
        )

        if checkpointSaved:
            commonKwargs = dict(
                updates=updateNumber,
                bestRate=bestRate,
                bestScore=bestScore,
                totalEpisodes=totalEpisodes,
                totalSteps=totalSteps,
                config={"learningRate": learningRate, "maxSteps": maxSteps, "episodesPerUpdate": episodesPerUpdate},
                version=version,
                modelId=modelId,
                trainingConfig=cfg,
                mapHistory=mapHistory,
                metricsHistory=tracker.history,
                freshInit=freshInit,
            )
            saveCheckpoint(checkpointPath, model, optimizer=optimizer, **commonKwargs)
            if bestSaved:
                saveCheckpoint(bestPath, model, optimizer=optimizer, **commonKwargs)
            try:
                logPath.parent.mkdir(parents=True, exist_ok=True)
                with logPath.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record) + "\n")
            except OSError:
                pass

        print(tracker.formatProgress(record), flush=True)

    if int(updates) >= 10 and (
        bestRate > lastEvalWin
        or (bestRate == lastEvalWin and bestScore is not None and lastEvalScore is not None and bestScore < lastEvalScore)
    ):
        model.load_state_dict(bestStateDict)
        if bestOptimizationState is not None:
            try:
                optimizer.load_state_dict(bestOptimizationState)
            except Exception:
                pass
        saveCheckpoint(
            checkpointPath,
            model,
            optimizer=optimizer,
            updates=startUpdate + int(updates),
            bestRate=bestRate,
            bestScore=bestScore,
            totalEpisodes=totalEpisodes,
            totalSteps=totalSteps,
            config={"learningRate": learningRate, "maxSteps": maxSteps, "episodesPerUpdate": episodesPerUpdate},
            version=version,
            modelId=modelId,
            trainingConfig=cfg,
            mapHistory=mapHistory,
            metricsHistory=tracker.history,
            freshInit=freshInit,
        )

    model.version = version
    model.modelId = modelId
    return model


import copy


def continualLearnStep(
    checkpoint,
    recentEpisodes=None,
    trainMapsFolder="maps/train",
    playedMapsFolder="maps/played",
    validationFolder="maps/validation",
    updates=None,
    rehearsalCount=4,
    maxSteps=300,
    learningRate=None,
    config=None,
):
    cfg = makeConfig(config)
    contCfg = cfg["continual"]
    ppoCfg = cfg["ppo"]
    rehCfg = cfg["rehearsal"]

    updates = int(updates if updates is not None else contCfg["updates"])
    learningRate = float(learningRate if learningRate is not None else contCfg["learningRate"])
    maxSteps = int(maxSteps)

    checkpointPath = Path(checkpoint)
    model = RecurrentPolicy(hiddenSize=ppoCfg["hiddenSize"])
    optimizer = torch.optim.Adam(model.parameters(), lr=learningRate)
    meta = loadCheckpointFull(checkpointPath, model, optimizer=optimizer, restoreRng=False)
    for group in optimizer.param_groups:
        group["lr"] = learningRate

    startUpdate = int(meta["updates"])
    bestRate = float(meta["bestRate"])
    bestScore = meta.get("bestScore", None)
    totalEpisodes = int(meta["totalEpisodes"])
    totalSteps = int(meta["totalSteps"])
    version = int(meta["version"])
    modelId = meta.get("modelId") or uuid.uuid4().hex[:12]
    mapHistory = dict(meta.get("mapHistory") or {})
    metricsHistory = list(meta.get("metricsHistory") or [])
    freshInit = meta.get("freshInit")
    preLearnStateDict = {k: v.detach().clone() for k, v in model.state_dict().items()}

    rehearsal = RehearsalManager(
        trainMapsFolder=trainMapsFolder,
        playedMapsFolder=playedMapsFolder,
        excludedFolders=["maps/test", validationFolder] if validationFolder else ["maps/test"],
    )

    trainMapSample = rehearsal.availableTrainMaps()[: int(rehCfg.get("retentionSampleSize", 10))]
    retentionBefore = (
        evaluate(model, trainMapSample, episodesPerMap=1, maxSteps=maxSteps, deterministic=True, modelVersion=version)
        if trainMapSample
        else None
    )

    lastMetrics = None
    for stepIdx in range(1, int(updates) + 1):
        updNum = startUpdate + stepIdx
        rc = rewardConfigForUpdate(cfg, updNum)
        rehearsalEpisodes = rehearsal.generateRehearsalEpisodes(
            model,
            count=max(2, int(rehearsalCount)),
            maxSteps=maxSteps,
            rewardConfig=rc,
            playedRatio=rehCfg.get("playedRatio", 0.4),
        )
        for ep in rehearsalEpisodes:
            totalEpisodes += 1
            totalSteps += ep["length"]

        batch = list(rehearsalEpisodes)
        if stepIdx == 1 and recentEpisodes:
            for ep in recentEpisodes:
                obsList = ep.get("observations", [])
                if len(ep.get("actions", [])) > 0 and obsList and len(obsList[0]) == model.observationSize:
                    batch.append(ep)
                    totalEpisodes += 1
                    totalSteps += len(ep["actions"])

        if not batch:
            break

        _updateMapHistory(mapHistory, batch)
        entCoef = entropyCoefficient(cfg, updNum)
        lastMetrics = updatePolicy(
            model,
            optimizer,
            batch,
            epochs=3,
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

    # Adaptive retention guard: if performance on old training maps dropped beyond tolerance,
    # run a rehearsal consolidation pass on old training maps.
    retentionAfter = (
        evaluate(model, trainMapSample, episodesPerMap=1, maxSteps=maxSteps, deterministic=True, modelVersion=version + 1)
        if trainMapSample
        else None
    )
    if (
        rehCfg.get("adaptive", True)
        and retentionBefore is not None
        and retentionAfter is not None
        and (retentionBefore["winRate"] - retentionAfter["winRate"]) > float(rehCfg.get("retentionTolerance", 0.10))
    ):
        rc = rewardConfigForUpdate(cfg, startUpdate + int(updates))
        consolidationEps = rehearsal.generateRehearsalEpisodes(
            model,
            count=max(4, int(rehearsalCount) * 2),
            maxSteps=maxSteps,
            rewardConfig=rc,
            playedRatio=0.0,
        )
        if consolidationEps:
            for ep in consolidationEps:
                totalEpisodes += 1
                totalSteps += ep["length"]
            _updateMapHistory(mapHistory, consolidationEps)
            lastMetrics = updatePolicy(model, optimizer, consolidationEps, epochs=2, entropyCoef=0.01)
            retentionAfter = evaluate(
                model, trainMapSample, episodesPerMap=1, maxSteps=maxSteps, deterministic=True, modelVersion=version + 1
            )
            if (retentionBefore["winRate"] - retentionAfter["winRate"]) > 0.25:
                # Blend 50% with pre-learn weights to prevent catastrophic forgetting
                with torch.no_grad():
                    for k, v in model.state_dict().items():
                        v.copy_(0.5 * preLearnStateDict[k] + 0.5 * v)

    updateNumber = startUpdate + int(updates)
    version += 1

    evalPaths = []
    if validationFolder and Path(validationFolder).exists():
        try:
            evalPaths = discoverMaps(validationFolder, excludedFolders=["maps/test"])
        except ValueError:
            evalPaths = []
    if not evalPaths:
        evalPaths = trainMapSample or rehearsal.availablePlayedMaps()[:8]

    evalMetrics = None
    bestSaved = False
    if evalPaths:
        evalMetrics = evaluate(model, evalPaths, episodesPerMap=1, maxSteps=maxSteps, deterministic=True, modelVersion=version)
        if evalMetrics["winRate"] > bestRate or (
            evalMetrics["winRate"] == bestRate and (bestScore is None or evalMetrics["meanScore"] <= bestScore)
        ):
            bestRate = evalMetrics["winRate"]
            bestScore = evalMetrics["meanScore"]
            bestSaved = True

    commonKwargs = dict(
        updates=updateNumber,
        bestRate=bestRate,
        bestScore=bestScore,
        totalEpisodes=totalEpisodes,
        totalSteps=totalSteps,
        config={"learningRate": learningRate, "maxSteps": maxSteps, "continual": True},
        version=version,
        modelId=modelId,
        trainingConfig=cfg,
        mapHistory=mapHistory,
        metricsHistory=metricsHistory,
        freshInit=freshInit,
    )
    saveCheckpoint(checkpointPath, model, optimizer=optimizer, **commonKwargs)
    if bestSaved:
        saveCheckpoint(bestCheckpointPath(checkpointPath), model, optimizer=optimizer, **commonKwargs)

    return {
        "modelId": modelId,
        "updates": updateNumber,
        "version": version,
        "bestRate": bestRate,
        "bestScore": bestScore,
        "totalEpisodes": totalEpisodes,
        "totalSteps": totalSteps,
        "loss": float(lastMetrics) if lastMetrics is not None else 0.0,
        "policyLoss": float(getattr(lastMetrics, "policyLoss", 0.0)) if lastMetrics is not None else 0.0,
        "valueLoss": float(getattr(lastMetrics, "valueLoss", 0.0)) if lastMetrics is not None else 0.0,
        "entropy": float(getattr(lastMetrics, "entropy", 0.0)) if lastMetrics is not None else 0.0,
        "evaluation": evalMetrics,
        "retention": retentionAfter,
    }
