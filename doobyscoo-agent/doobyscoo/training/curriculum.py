import random
from pathlib import Path


class BalancedMapSampler:
    def __init__(self, mapPaths):
        self.mapPaths = [Path(p) for p in mapPaths]
        if not self.mapPaths:
            raise ValueError("BalancedMapSampler requires at least one map path")
        self.playCounts = {p: 0 for p in self.mapPaths}
        self.winRates = {p: 0.5 for p in self.mapPaths}
        self.meanScores = {p: 50.0 for p in self.mapPaths}

    def addMaps(self, newPaths):
        for p in newPaths:
            pathObj = Path(p)
            if pathObj not in self.playCounts:
                self.mapPaths.append(pathObj)
                self.playCounts[pathObj] = 0
                self.winRates[pathObj] = 0.5
                self.meanScores[pathObj] = 50.0

    def recordOutcome(self, path, won, score):
        pathObj = Path(path)
        if pathObj not in self.playCounts:
            self.addMaps([pathObj])
        self.playCounts[pathObj] += 1
        alpha = 0.25
        self.winRates[pathObj] = (1.0 - alpha) * self.winRates[pathObj] + alpha * float(bool(won))
        self.meanScores[pathObj] = (1.0 - alpha) * self.meanScores[pathObj] + alpha * float(score)

    def sample(self, count=1):
        weights = []
        minPlays = min(self.playCounts.values()) if self.playCounts else 0
        for p in self.mapPaths:
            exposureFactor = 1.0 / (1.0 + 0.25 * (self.playCounts[p] - minPlays))
            difficultyFactor = 1.2 - 0.7 * self.winRates[p]
            weights.append(max(0.1, exposureFactor * difficultyFactor))
        chosen = random.choices(self.mapPaths, weights=weights, k=count)
        return chosen if count > 1 else chosen[0]

