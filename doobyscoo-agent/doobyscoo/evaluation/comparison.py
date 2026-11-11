from pathlib import Path
from ..agent.network import RecurrentPolicy
from ..storage.checkpoint import loadCheckpointFull
from .evaluator import evaluate


def compareModels(modelsOrPaths, testPaths, episodesPerMap=1, maxSteps=300):
    summary = {}
    for label, item in modelsOrPaths.items():
        if isinstance(item, RecurrentPolicy):
            model = item
            version = getattr(model, "version", 0)
        elif item is None or item == "untrained":
            model = RecurrentPolicy()
            version = 0
        else:
            model = RecurrentPolicy()
            meta = loadCheckpointFull(Path(item), model)
            version = meta.get("version", 0)
        metrics = evaluate(model, testPaths, episodesPerMap=episodesPerMap, maxSteps=maxSteps, modelVersion=version)
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
            comparison["improvements"][f"{baseLabel}_to_{otherLabel}"] = {
                "winRateDelta": float(winDelta),
                "meanScoreDelta": float(scoreDelta),
                "improved": (winDelta > 0.0) or (winDelta == 0.0 and scoreDelta <= 0.0),
            }
    return comparison

