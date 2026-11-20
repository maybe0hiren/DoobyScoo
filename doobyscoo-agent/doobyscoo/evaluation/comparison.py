import random
from pathlib import Path
import numpy as np
from ..agent.network import RecurrentPolicy
from ..environment.maze_environment import MazeEnvironment, loadMaze
from ..storage.checkpoint import loadCheckpointFull
from .evaluator import evaluate


def _runNonNeuralBaseline(kind, paths, maxSteps=300, seed=42):
    """Run a non-neural baseline ('random' legal moves or 'heuristic' greedy Manhattan)
    across `paths` under strict partial observability."""
    rng = random.Random(seed)
    episodes = []
    for idx, item in enumerate(paths):
        mazeData = item if isinstance(item, dict) else loadMaze(item)
        mapName = item.get("metadata", {}).get("maze_name", f"map_{idx}") if isinstance(item, dict) else Path(item).name
        env = MazeEnvironment(mazeData, maxSteps=maxSteps, enforceScoreLimit=True)
        env.reset()
        while not env.done:
            legal = env.availableActionIndices()
            if not legal:
                act = 0
            elif kind == "random":
                act = rng.choice(legal)
            else:
                # Simple greedy heuristic: move toward nearest End or uncollected Bone by Manhattan distance
                # without oscillation detection, dead-end pruning, or score-detour awareness.
                targets = list(env.remainingBones) if env.remainingBones else list(env.ends)
                nearest = min(targets, key=lambda t: abs(t[0] - env.position[0]) + abs(t[1] - env.position[1]))
                bestAct = legal[0]
                bestDist = 999999
                for a in legal:
                    nb = env.neighbor(a)
                    if nb is not None:
                        d = abs(nb[0] - nearest[0]) + abs(nb[1] - nearest[1])
                        if d < bestDist:
                            bestDist = d
                            bestAct = a
                act = bestAct
            env.step(act)
        episodes.append({
            "sourceMap": mapName,
            "won": bool(env.position in env.ends and not env.scoreLimitExceeded),
            "timeout": bool((env.position not in env.ends) and not env.scoreLimitExceeded and env.steps >= env.maxSteps),
            "scoreLimitExceeded": bool(env.scoreLimitExceeded),
            "score": int(env.currentScore()),
            "trainingScore": int(env.currentTrainingScore()),
            "length": int(env.steps),
            "bonesCollected": int(env.bonesCollected()),
            "totalBones": len(env.bones),
            "revisits": int(env.revisits),
            "uniqueCells": len(env.visitCounts),
            "deadEndsEncountered": int(env.deadEndsEncountered),
            "repeatedMistakes": int(env.totalMistakesCount()),
            "oscillationsDetected": int(env.oscillationsDetected),
            "maxVisitCount": int(env.maxVisitCount()),
            "wallBumps": int(env.wallBumps),
            "totalReward": float(env.cumulativeReward),
        })

    wins = [1.0 if e["won"] else 0.0 for e in episodes]
    scores = [e["score"] for e in episodes]
    steps = [e["length"] for e in episodes]
    bones = [e["bonesCollected"] for e in episodes]
    totalBones = [e["totalBones"] for e in episodes]
    revisits = [e["revisits"] for e in episodes]
    revRates = [e["revisits"] / float(max(1, e["length"])) for e in episodes]
    return {
        "winRate": float(np.mean(wins)) if wins else 0.0,
        "mazeCompletionRate": float(np.mean(wins)) if wins else 0.0,
        "meanScore": float(np.mean(scores)) if scores else 0.0,
        "meanSteps": float(np.mean(steps)) if steps else 0.0,
        "bonesCollected": float(np.mean(bones)) if bones else 0.0,
        "boneCollectionRate": float(sum(bones)) / float(max(1, sum(totalBones))),
        "meanRevisits": float(np.mean(revisits)) if revisits else 0.0,
        "revisitRate": float(np.mean(revRates)) if revRates else 0.0,
        "repeatedMoves": int(sum(e["repeatedMistakes"] for e in episodes)),
        "loopsDetected": int(sum(e["oscillationsDetected"] for e in episodes)),
        "maxVisitCount": int(max((e["maxVisitCount"] for e in episodes), default=0)),
        "episodes": len(episodes),
    }


def compareModels(modelsOrPaths, testPaths, episodesPerMap=1, maxSteps=300, deterministic=True):
    summary = {}
    for label, item in modelsOrPaths.items():
        if isinstance(item, str) and item in ("random", "heuristic"):
            summary[label] = _runNonNeuralBaseline(item, testPaths, maxSteps=maxSteps)
            continue
        if isinstance(item, RecurrentPolicy):
            model = item
            version = getattr(model, "version", 0)
        elif item is None or item == "untrained":
            model = RecurrentPolicy()
            model.isUntrainedBaseline = True
            version = 0
        else:
            model = RecurrentPolicy()
            meta = loadCheckpointFull(Path(item), model)
            version = meta.get("version", 0)
            if int(meta.get("updates", 0)) == 0:
                model.isUntrainedBaseline = True
        metrics = evaluate(
            model,
            testPaths,
            episodesPerMap=episodesPerMap,
            maxSteps=maxSteps,
            deterministic=deterministic,
            modelVersion=version,
        )
        summary[label] = metrics

    labels = list(summary.keys())
    comparison = {"models": summary, "improvements": {}}
    if len(labels) >= 2:
        baseLabel = labels[0]
        baseMetrics = summary[baseLabel]
        for otherLabel in labels[1:]:
            otherMetrics = summary[otherLabel]
            winDelta = otherMetrics["winRate"] - baseMetrics["winRate"]
            scoreDelta = otherMetrics["meanScore"] - baseMetrics["meanScore"]
            boneDelta = otherMetrics["bonesCollected"] - baseMetrics["bonesCollected"]
            revisitDelta = otherMetrics["revisitRate"] - baseMetrics["revisitRate"]
            comparison["improvements"][f"{baseLabel}_to_{otherLabel}"] = {
                "winRateDelta": float(winDelta),
                "meanScoreDelta": float(scoreDelta),
                "bonesCollectedDelta": float(boneDelta),
                "revisitRateDelta": float(revisitDelta),
                "improved": (winDelta > 0.0) or (winDelta == 0.0 and scoreDelta <= 0.0),
            }
    return comparison

