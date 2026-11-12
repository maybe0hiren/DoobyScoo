import random
from pathlib import Path


class BalancedMapSampler:
    """Diverse map sampling.

    Maps are drawn from a shuffled deck without replacement, so every map is
    played once per pass in a fresh random order and no small subset dominates.
    A configurable share of each batch is reserved for maps the Dog is
    currently struggling on (low running win rate).
    """

    def __init__(self, mapPaths, struggleFraction=0.25, uniqueMapsPerBatch=True, rng=None):
        self.mapPaths = []
        self.playCounts = {}
        self.winRates = {}
        self.meanScores = {}
        self.struggleFraction = float(struggleFraction)
        self.uniqueMapsPerBatch = bool(uniqueMapsPerBatch)
        self.rng = rng or random.Random()
        self.deck = []
        self.addMaps(mapPaths)
        if not self.mapPaths:
            raise ValueError("BalancedMapSampler requires at least one map path")

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

    def _drawFromDeck(self, exclude):
        for _ in range(2):
            if not self.deck:
                self.deck = list(self.mapPaths)
                self.rng.shuffle(self.deck)
            for idx, path in enumerate(self.deck):
                if path not in exclude:
                    return self.deck.pop(idx)
            if not self.uniqueMapsPerBatch:
                break
            self.deck = []
        return self.deck.pop() if self.deck else self.rng.choice(self.mapPaths)

    def sample(self, count=1):
        count = int(count)
        chosen = []
        struggleSlots = int(round(count * self.struggleFraction)) if len(self.mapPaths) > 1 else 0
        for _ in range(count - struggleSlots):
            exclude = set(chosen) if self.uniqueMapsPerBatch and len(chosen) < len(self.mapPaths) else set()
            chosen.append(self._drawFromDeck(exclude))
        if struggleSlots:
            weights = [max(0.05, 1.0 - self.winRates[p]) for p in self.mapPaths]
            chosen.extend(self.rng.choices(self.mapPaths, weights=weights, k=struggleSlots))
        self.rng.shuffle(chosen)
        return chosen if count > 1 else chosen[0]
