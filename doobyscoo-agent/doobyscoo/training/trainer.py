from pathlib import Path
import torch
from ..agent.network import RecurrentPolicy
from ..agent.ppo import updatePolicy
from ..environment.maze_environment import loadMaze
from ..evaluation.evaluator import evaluate
from ..storage.checkpoint import loadCheckpointFull, saveCheckpoint
from .curriculum import BalancedMapSampler
from .metrics import TrainingMetricsTracker
from .rehearsal import RehearsalManager
from .rollout import collectEpisode, discoverMaps


def train(
    mapsFolder,
    checkpoint="models/dog.pt",
    updates=100,
    episodesPerUpdate=8,
    maxSteps=300,
    learningRate=3e-4,
    rehearsalFolder=None,
    validationFolder=None,
    resume=True,
    cpuThreads=4,
):
    if cpuThreads and cpuThreads > 0:
        torch.set_num_threads(min(int(cpuThreads), max(1, torch.get_num_threads())))

    excluded = ["maps/test"]
    if validationFolder:
        excluded.append(validationFolder)

    paths = discoverMaps(mapsFolder, excludedFolders=excluded)
    if rehearsalFolder and Path(rehearsalFolder).exists():
        try:
            rehearsalPaths = discoverMaps(rehearsalFolder, excludedFolders=excluded)
            paths = list(dict.fromkeys(paths + rehearsalPaths))
        except ValueError:
            pass

    valPaths = []
    if validationFolder and Path(validationFolder).exists():
        try:
            valPaths = discoverMaps(validationFolder, excludedFolders=["maps/test"])
        except ValueError:
            valPaths = []
    if not valPaths:
        valPaths = paths

    model = RecurrentPolicy()
    optimizer = torch.optim.Adam(model.parameters(), lr=learningRate)

    if resume and Path(checkpoint).exists():
        meta = loadCheckpointFull(checkpoint, model, optimizer=optimizer, restoreRng=False)
        startUpdate = int(meta["updates"])
        bestRate = float(meta["bestRate"])
        bestScore = meta.get("bestScore", None)
        totalEpisodes = int(meta["totalEpisodes"])
        totalSteps = int(meta["totalSteps"])
        version = int(meta["version"])
    else:
        startUpdate = 0
        bestRate = 0.0
        bestScore = None
        totalEpisodes = 0
        totalSteps = 0
        version = 0

    sampler = BalancedMapSampler(paths)
    tracker = TrainingMetricsTracker()
    bestStateDict = {k: v.detach().clone() for k, v in model.state_dict().items()}

    print(
        f"Maps: {len(paths)} | Resuming from update: {startUpdate} | Episodes: {totalEpisodes} | Device: CPU",
        flush=True,
    )

    lastEvalWin = 0.0
    for updateIndex in range(1, int(updates) + 1):
        model.eval()
        sampledPaths = sampler.sample(count=episodesPerUpdate)
        if not isinstance(sampledPaths, list):
            sampledPaths = [sampledPaths]

        episodes = []
        for mapPath in sampledPaths:
            ep = collectEpisode(model, loadMaze(mapPath), maxSteps=maxSteps, deterministic=False)
            sampler.recordOutcome(mapPath, ep["won"], ep["score"])
            episodes.append(ep)
            totalEpisodes += 1
            totalSteps += ep["length"]

        model.train()
        lossMetrics = updatePolicy(model, optimizer, episodes)
        updateNumber = startUpdate + updateIndex

        evalMetrics = None
        checkpointSaved = False
        if updateIndex % 5 == 0 or updateIndex == updates:
            evalMetrics = evaluate(model, valPaths, episodesPerMap=1, maxSteps=maxSteps, modelVersion=version + 1)
            evalWin = evalMetrics["winRate"]
            evalScore = evalMetrics["meanScore"]
            lastEvalWin = evalWin
            if evalWin > bestRate or (evalWin == bestRate and (bestScore is None or evalScore <= bestScore)):
                bestRate = evalWin
                bestScore = evalScore
                bestStateDict = {k: v.detach().clone() for k, v in model.state_dict().items()}
            version += 1
            saveCheckpoint(
                checkpoint,
                model,
                optimizer=optimizer,
                updates=updateNumber,
                bestRate=bestRate,
                bestScore=bestScore,
                totalEpisodes=totalEpisodes,
                totalSteps=totalSteps,
                config={"learningRate": learningRate, "maxSteps": maxSteps, "episodesPerUpdate": episodesPerUpdate},
                version=version,
            )
            checkpointSaved = True

        record = tracker.summarizeBatch(
            updateNumber=updateNumber,
            numMaps=len(paths),
            totalEpisodes=totalEpisodes,
            episodes=episodes,
            updateMetrics=lossMetrics,
            evalMetrics=evalMetrics,
            checkpointSaved=checkpointSaved,
        )
        print(tracker.formatProgress(record), flush=True)

    if updates >= 10 and bestRate > lastEvalWin:
        model.load_state_dict(bestStateDict)
        saveCheckpoint(
            checkpoint,
            model,
            optimizer=optimizer,
            updates=startUpdate + int(updates),
            bestRate=bestRate,
            bestScore=bestScore,
            totalEpisodes=totalEpisodes,
            totalSteps=totalSteps,
            config={"learningRate": learningRate, "maxSteps": maxSteps, "episodesPerUpdate": episodesPerUpdate},
            version=version,
        )

    model.version = version
    return model


def continualLearnStep(
    checkpoint,
    recentEpisodes=None,
    trainMapsFolder="maps/train",
    playedMapsFolder="maps/played",
    validationFolder="maps/validation",
    updates=3,
    rehearsalCount=4,
    maxSteps=300,
    learningRate=2e-4,
):
    model = RecurrentPolicy()
    optimizer = torch.optim.Adam(model.parameters(), lr=learningRate)
    meta = loadCheckpointFull(checkpoint, model, optimizer=optimizer, restoreRng=False)
    startUpdate = int(meta["updates"])
    bestRate = float(meta["bestRate"])
    bestScore = meta.get("bestScore", None)
    totalEpisodes = int(meta["totalEpisodes"])
    totalSteps = int(meta["totalSteps"])
    version = int(meta["version"])

    rehearsal = RehearsalManager(
        trainMapsFolder=trainMapsFolder,
        playedMapsFolder=playedMapsFolder,
        excludedFolders=["maps/test", validationFolder] if validationFolder else ["maps/test"],
    )

    lastMetrics = None
    for stepIdx in range(1, int(updates) + 1):
        model.eval()
        rehearsalEpisodes = rehearsal.generateRehearsalEpisodes(model, count=rehearsalCount, maxSteps=maxSteps)
        for ep in rehearsalEpisodes:
            totalEpisodes += 1
            totalSteps += ep["length"]

        batch = list(rehearsalEpisodes)
        if stepIdx == 1 and recentEpisodes:
            for ep in recentEpisodes:
                if len(ep.get("actions", [])) > 0:
                    batch.append(ep)
                    totalEpisodes += 1
                    totalSteps += len(ep["actions"])

        if not batch:
            break

        model.train()
        lastMetrics = updatePolicy(model, optimizer, batch, epochs=3)

    updateNumber = startUpdate + int(updates)
    version += 1

    evalPaths = []
    if validationFolder and Path(validationFolder).exists():
        try:
            evalPaths = discoverMaps(validationFolder, excludedFolders=["maps/test"])
        except ValueError:
            evalPaths = []
    if not evalPaths:
        evalPaths = rehearsal.availableTrainMaps()[:8] or rehearsal.availablePlayedMaps()[:8]

    evalMetrics = None
    if evalPaths:
        evalMetrics = evaluate(model, evalPaths, episodesPerMap=1, maxSteps=maxSteps, modelVersion=version)
        if evalMetrics["winRate"] >= bestRate:
            bestRate = evalMetrics["winRate"]
            if bestScore is None or evalMetrics["meanScore"] < bestScore:
                bestScore = evalMetrics["meanScore"]

    saveCheckpoint(
        checkpoint,
        model,
        optimizer=optimizer,
        updates=updateNumber,
        bestRate=bestRate,
        bestScore=bestScore,
        totalEpisodes=totalEpisodes,
        totalSteps=totalSteps,
        config={"learningRate": learningRate, "maxSteps": maxSteps, "continual": True},
        version=version,
    )

    return {
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
    }
