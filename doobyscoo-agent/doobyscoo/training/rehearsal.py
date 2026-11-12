import json
import random
from pathlib import Path
from ..environment.maze_environment import loadMaze
from ..environment.validation import validateMaze
from .rollout import collectEpisodes, gridHash


class RehearsalManager:
    """Pool of previously learned maps that are re-practised with FRESH on-policy rollouts.

    PPO is on-policy, so stale transitions are never replayed; instead the
    current policy is rolled out again on old maps and those new trajectories
    are mixed into each update. Test and validation maps can never enter the
    pool (excluded by folder and by grid hash).
    """

    def __init__(self, trainMapsFolder="maps/train", playedMapsFolder="maps/played", excludedFolders=None,
                 extraMaps=None, excludedHashes=None, rng=None):
        self.trainMapsFolder = Path(trainMapsFolder) if trainMapsFolder else None
        self.playedMapsFolder = Path(playedMapsFolder) if playedMapsFolder else None
        defaultExcluded = ["maps/test", "maps/validation"]
        if excludedFolders:
            defaultExcluded.extend(excludedFolders)
        self.excludedFolders = [Path(f).resolve() for f in defaultExcluded if f is not None]
        self.excludedHashes = set(excludedHashes or [])
        self.extraMaps = [Path(p) for p in (extraMaps or [])]
        self.winHistory = {}
        self.rng = rng or random.Random()

    def isExcluded(self, path):
        resolved = Path(path).resolve()
        for ex in self.excludedFolders:
            if resolved == ex or ex in resolved.parents:
                return True
        if "test" in resolved.parts or "validation" in resolved.parts:
            return True
        return False

    def _validPath(self, path):
        if self.isExcluded(path):
            return False
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            return False
        if not validateMaze(data)["valid"]:
            return False
        return gridHash(data) not in self.excludedHashes

    def _discoverSafe(self, folder):
        if folder is None or not Path(folder).exists():
            return []
        return [p for p in sorted(Path(folder).rglob("*.json")) if self._validPath(p)]

    def availableTrainMaps(self):
        maps = self._discoverSafe(self.trainMapsFolder)
        known = {p.resolve() for p in maps}
        for p in self.extraMaps:
            if p.exists() and p.resolve() not in known and self._validPath(p):
                maps.append(p)
                known.add(p.resolve())
        return maps

    def availablePlayedMaps(self):
        return self._discoverSafe(self.playedMapsFolder)

    def addMaps(self, paths):
        for p in paths:
            p = Path(p)
            if p not in self.extraMaps:
                self.extraMaps.append(p)

    def sampleRehearsalMaps(self, count=4, playedRatio=0.4):
        trainPaths = self.availableTrainMaps()
        playedPaths = self.availablePlayedMaps()
        if not trainPaths and not playedPaths or count <= 0:
            return []
        selected = []
        playedTarget = int(round(count * playedRatio)) if playedPaths else 0
        if not trainPaths:
            playedTarget = count
        if playedTarget > 0:
            selected.extend(self._weightedSample(playedPaths, playedTarget))
        remaining = count - len(selected)
        if remaining > 0:
            selected.extend(self._weightedSample(trainPaths or playedPaths, remaining))
        return selected

    def _weightedSample(self, paths, count):
        # Favour maps whose recent rehearsal went badly, but keep every map reachable.
        weights = [max(0.2, 1.3 - 0.8 * self.winHistory.get(str(p), 0.5)) for p in paths]
        if count <= len(paths):
            pool, w, out = list(paths), list(weights), []
            for _ in range(count):
                pick = self.rng.choices(range(len(pool)), weights=w, k=1)[0]
                out.append(pool.pop(pick))
                w.pop(pick)
            return out
        return self.rng.choices(paths, weights=weights, k=count)

    def recordOutcome(self, path, won):
        prev = self.winHistory.get(str(path), 0.5)
        self.winHistory[str(path)] = 0.75 * prev + 0.25 * float(won)

    def generateRehearsalEpisodes(self, model, count=4, maxSteps=300, rewardConfig=None, playedRatio=0.4):
        sampledPaths = self.sampleRehearsalMaps(count=count, playedRatio=playedRatio)
        if not sampledPaths:
            return []
        episodes = collectEpisodes(model, sampledPaths, maxSteps=maxSteps, deterministic=False, rewardConfig=rewardConfig)
        for path, ep in zip(sampledPaths, episodes):
            ep["sourceMap"] = str(Path(path).name)
            ep["sourcePath"] = str(path)
            ep["rehearsal"] = True
            self.recordOutcome(path, ep["won"])
        return episodes
