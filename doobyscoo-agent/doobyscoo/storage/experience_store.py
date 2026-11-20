import hashlib
import json
from pathlib import Path
from ..environment.validation import validateMaze


class ExperienceStore:
    def __init__(self, playedMapsFolder="maps/played", excludedFolders=None, maxBufferEpisodes=64):
        self.playedMapsFolder = Path(playedMapsFolder)
        self.playedMapsFolder.mkdir(parents=True, exist_ok=True)
        defaultExcluded = ["maps/test", "maps/validation"]
        if excludedFolders:
            defaultExcluded.extend(excludedFolders)
        self.excludedFolders = [Path(f).resolve() for f in defaultExcluded if f is not None]
        self.excludedHashes = set()
        self.maxBufferEpisodes = int(maxBufferEpisodes)
        self.episodeBuffer = []
        self.totalRecordedEpisodes = 0
        self.totalRecordedSteps = 0
        self.staleDroppedCount = 0
        self.mapPlayCounts = {}
        self.hashIndex = {}
        self._indexExcludedHashes()
        self._indexExistingPlayedMaps()

    def _gridHash(self, mazeData):
        canonical = json.dumps(mazeData.get("grid", []), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def _indexExcludedHashes(self):
        for ex in self.excludedFolders:
            if ex.exists() and ex.is_dir():
                for path in ex.rglob("*.json"):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if isinstance(data, dict) and "grid" in data:
                            self.excludedHashes.add(self._gridHash(data))
                    except Exception:
                        continue

    def _isExcludedPath(self, path):
        if path is None:
            return False
        resolved = Path(path).resolve()
        for excluded in self.excludedFolders:
            if resolved == excluded or excluded in resolved.parents:
                return True
        if "test" in resolved.parts or "validation" in resolved.parts:
            return True
        return False

    def _indexExistingPlayedMaps(self):
        for path in sorted(self.playedMapsFolder.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if validateMaze(data)["valid"]:
                    gridHash = self._gridHash(data)
                    if gridHash not in self.excludedHashes:
                        self.hashIndex[gridHash] = path
            except Exception:
                continue

    def registerPlayedMap(self, mazeData, sourcePath=None, isTestMap=False):
        if isTestMap or self._isExcludedPath(sourcePath):
            return None
        validation = validateMaze(mazeData)
        if not validation["valid"]:
            return None
        gridHash = self._gridHash(mazeData)
        if gridHash in self.excludedHashes:
            return None
        self.mapPlayCounts[gridHash] = self.mapPlayCounts.get(gridHash, 0) + 1
        if gridHash in self.hashIndex and self.hashIndex[gridHash].exists():
            return self.hashIndex[gridHash]

        index = len(self.hashIndex) + 1
        targetPath = self.playedMapsFolder / f"played_{index:06d}.json"
        while targetPath.exists():
            index += 1
            targetPath = self.playedMapsFolder / f"played_{index:06d}.json"

        payload = dict(mazeData)
        metadata = dict(payload.get("metadata", {}))
        metadata.setdefault("maze_name", targetPath.stem)
        metadata["grid_hash"] = gridHash
        payload["metadata"] = metadata
        targetPath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.hashIndex[gridHash] = targetPath
        return targetPath

    def addEpisode(self, episode, mazeData=None, sourcePath=None, isTestMap=False, currentModelVersion=None):
        if isTestMap or self._isExcludedPath(sourcePath):
            return None
        if mazeData is not None and self._gridHash(mazeData) in self.excludedHashes:
            return None
        savedPath = None
        if mazeData is not None:
            savedPath = self.registerPlayedMap(mazeData, sourcePath=sourcePath, isTestMap=isTestMap)
        if episode and len(episode.get("actions", [])) > 0:
            if currentModelVersion is not None:
                epVer = episode.get("modelVersion")
                if epVer is not None and int(epVer) != int(currentModelVersion):
                    self.staleDroppedCount += 1
                    return savedPath
                episode["modelVersion"] = int(currentModelVersion)
            self.episodeBuffer.append(episode)
            self.totalRecordedEpisodes += 1
            self.totalRecordedSteps += len(episode.get("actions", []))
            if len(self.episodeBuffer) > self.maxBufferEpisodes:
                self.episodeBuffer.pop(0)
        return savedPath

    def pendingCount(self):
        return len(self.episodeBuffer)

    def pendingSamplesCount(self):
        return int(sum(len(ep.get("actions", [])) for ep in self.episodeBuffer))

    def clearStaleEpisodes(self, activeModelVersion):
        """Remove any buffered trajectories collected under an older policy version
        so PPO updates strictly use fresh on-policy rollouts."""
        if activeModelVersion is None:
            return 0
        kept = []
        dropped = 0
        for ep in self.episodeBuffer:
            epVer = ep.get("modelVersion")
            if epVer is None or int(epVer) == int(activeModelVersion):
                kept.append(ep)
            else:
                dropped += 1
        self.episodeBuffer = kept
        self.staleDroppedCount += dropped
        return dropped

    def popEpisodes(self, maxCount=None, requiredModelVersion=None):
        if requiredModelVersion is not None:
            self.clearStaleEpisodes(requiredModelVersion)
        if maxCount is None or maxCount >= len(self.episodeBuffer):
            batch = list(self.episodeBuffer)
            self.episodeBuffer.clear()
            return batch
        batch = self.episodeBuffer[:maxCount]
        self.episodeBuffer = self.episodeBuffer[maxCount:]
        return batch

    def listPlayedMaps(self):
        validPaths = []
        for path in sorted(self.playedMapsFolder.glob("*.json")):
            if self._isExcludedPath(path):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if validateMaze(data)["valid"] and self._gridHash(data) not in self.excludedHashes:
                    validPaths.append(path)
            except Exception:
                continue
        return validPaths

