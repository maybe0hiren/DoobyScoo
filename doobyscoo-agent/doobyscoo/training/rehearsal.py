import json
import random
from pathlib import Path
from ..environment.maze_environment import loadMaze
from ..environment.validation import validateMaze
from .rollout import collectEpisode


class RehearsalManager:
    def __init__(self, trainMapsFolder="maps/train", playedMapsFolder="maps/played", excludedFolders=None):
        self.trainMapsFolder = Path(trainMapsFolder) if trainMapsFolder else None
        self.playedMapsFolder = Path(playedMapsFolder) if playedMapsFolder else None
        defaultExcluded = ["maps/test", "maps/validation"]
        if excludedFolders:
            defaultExcluded.extend(excludedFolders)
        self.excludedFolders = [Path(f).resolve() for f in defaultExcluded if f is not None]
        self.winHistory = {}

    def isExcluded(self, path):
        resolved = Path(path).resolve()
        for ex in self.excludedFolders:
            if resolved == ex or ex in resolved.parents:
                return True
        if "test" in resolved.parts or "validation" in resolved.parts:
            return True
        return False

    def _discoverSafe(self, folder):
        if folder is None or not Path(folder).exists():
            return []
        valid = []
        for path in sorted(Path(folder).rglob("*.json")):
            if self.isExcluded(path):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if validateMaze(data)["valid"]:
                    valid.append(path)
            except Exception:
                continue
        return valid

    def availableTrainMaps(self):
        return self._discoverSafe(self.trainMapsFolder)

    def availablePlayedMaps(self):
        return self._discoverSafe(self.playedMapsFolder)

    def sampleRehearsalMaps(self, count=4, playedRatio=0.4):
        trainPaths = self.availableTrainMaps()
        playedPaths = self.availablePlayedMaps()
        if not trainPaths and not playedPaths:
            return []
        selected = []
        playedTarget = int(round(count * playedRatio)) if playedPaths else 0
        if not trainPaths:
            playedTarget = count

        if playedTarget > 0 and playedPaths:
            selected.extend(self._weightedSample(playedPaths, playedTarget))
        remaining = count - len(selected)
        if remaining > 0 and trainPaths:
            selected.extend(self._weightedSample(trainPaths, remaining))
        elif remaining > 0 and playedPaths:
            selected.extend(self._weightedSample(playedPaths, remaining))
        return selected

    def _weightedSample(self, paths, count):
        weights = []
        for p in paths:
            winRate = self.winHistory.get(str(p), 0.5)
            weights.append(max(0.2, 1.3 - 0.8 * winRate))
        return random.choices(paths, weights=weights, k=count)

    def generateRehearsalEpisodes(self, model, count=4, maxSteps=300):
        sampledPaths = self.sampleRehearsalMaps(count=count)
        episodes = []
        for path in sampledPaths:
            mazeData = loadMaze(path)
            ep = collectEpisode(model, mazeData, maxSteps=maxSteps, deterministic=False)
            ep["sourceMap"] = str(path.name)
            prevRate = self.winHistory.get(str(path), 0.5)
            self.winHistory[str(path)] = 0.75 * prevRate + 0.25 * float(ep["won"])
            episodes.append(ep)
        return episodes

