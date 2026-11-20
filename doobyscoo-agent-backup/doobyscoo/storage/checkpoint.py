import random
import shutil
import time
import uuid
from pathlib import Path
import numpy as np
import torch

CHECKPOINT_FORMAT = 4


class IncompatibleCheckpointError(RuntimeError):
    pass


def _readPayload(path):
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def bestCheckpointPath(path):
    path = Path(path)
    return path.with_name(f"{path.stem}_best{path.suffix}")


def metricsLogPath(path):
    path = Path(path)
    return path.with_name(f"{path.stem}_metrics.jsonl")


def _emptyMeta():
    return {
        "exists": False,
        "loaded": False,
        "updates": 0,
        "version": 0,
        "totalEpisodes": 0,
        "totalSteps": 0,
        "bestRate": 0.0,
        "bestScore": None,
        "config": {},
        "trainingConfig": None,
        "modelId": None,
        "architecture": None,
        "mapHistory": {},
        "metricsHistory": [],
        "optimizationState": {},
        "progressHistory": [],
        "freshInit": None,
    }


def _metaFromPayload(payload):
    return {
        "exists": True,
        "loaded": True,
        "updates": int(payload.get("updates", 0)),
        "version": int(payload.get("version", payload.get("updates", 1))),
        "totalEpisodes": int(payload.get("totalEpisodes", 0)),
        "totalSteps": int(payload.get("totalSteps", 0)),
        "bestRate": float(payload.get("bestRate", 0.0)),
        "bestScore": payload.get("bestScore", None),
        "config": payload.get("config", {}),
        "trainingConfig": payload.get("trainingConfig"),
        "modelId": payload.get("modelId"),
        "architecture": payload.get("config", {}).get("architecture"),
        "mapHistory": payload.get("mapHistory", {}) or {},
        "metricsHistory": payload.get("metricsHistory", []) or [],
        "optimizationState": payload.get("optimizationState", {}) or {},
        "progressHistory": payload.get("progressHistory", []) or [],
        "freshInit": payload.get("freshInit"),
        "timestamp": payload.get("timestamp"),
    }


def getCheckpointMetadata(path):
    path = Path(path)
    if not path.exists():
        return _emptyMeta()
    try:
        return _metaFromPayload(_readPayload(path))
    except Exception:
        return _emptyMeta()


def checkCompatibility(payload, model):
    config = payload.get("config", {}) if isinstance(payload, dict) else {}
    expected = getattr(model, "architecture", None)
    found = config.get("architecture")
    if expected and found != expected:
        raise IncompatibleCheckpointError(
            f"Checkpoint architecture '{found or 'legacy-v1'}' does not match current '{expected}'. "
            "Old models are never partially loaded; train a fresh model with `python -m doobyscoo train --fresh`."
        )
    expectedObs = getattr(model, "observationSize", None)
    foundObs = config.get("observationSize")
    if expectedObs and foundObs is not None and int(foundObs) != int(expectedObs):
        raise IncompatibleCheckpointError(
            f"Checkpoint observationSize '{foundObs}' does not match current '{expectedObs}'."
        )
    stateDict = payload.get("model", {})
    currentDict = model.state_dict()
    mismatched = [k for k, v in stateDict.items() if k not in currentDict or currentDict[k].shape != v.shape]
    missing = [k for k in currentDict if k not in stateDict]
    if mismatched or missing:
        raise IncompatibleCheckpointError(
            f"Checkpoint tensors do not match the current network (mismatched={mismatched[:3]}, missing={missing[:3]})."
        )


def saveCheckpoint(
    path,
    model,
    optimizer=None,
    updates=0,
    bestRate=0.0,
    bestScore=None,
    totalEpisodes=0,
    totalSteps=0,
    config=None,
    version=None,
    saveRng=True,
    modelId=None,
    trainingConfig=None,
    mapHistory=None,
    metricsHistory=None,
    optimizationState=None,
    progressHistory=None,
    freshInit=None,
):
    """Atomically write a checkpoint (temp file + rename; previous file kept as .bak)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previousMeta = getCheckpointMetadata(path)
    sameLineage = modelId is not None and previousMeta.get("modelId") == modelId
    if version is None:
        version = int(previousMeta.get("version", 0)) + 1 if sameLineage else 1
    if modelId is None:
        modelId = previousMeta.get("modelId") or uuid.uuid4().hex[:12]
    if freshInit is None and previousMeta.get("modelId") == modelId:
        freshInit = previousMeta.get("freshInit")

    modelConfig = {
        "architecture": getattr(model, "architecture", None),
        "observationSize": getattr(model, "observationSize", None),
        "hiddenSize": getattr(model, "hiddenSize", 128),
        "format": CHECKPOINT_FORMAT,
    }
    if isinstance(config, dict):
        modelConfig.update({k: v for k, v in config.items() if k not in ("architecture", "observationSize", "hiddenSize")})

    payload = {
        "model": model.state_dict(),
        "modelId": modelId,
        "updates": int(updates),
        "version": int(version),
        "bestRate": float(bestRate),
        "bestScore": float(bestScore) if bestScore is not None else None,
        "totalEpisodes": int(totalEpisodes),
        "totalSteps": int(totalSteps),
        "config": modelConfig,
        "trainingConfig": trainingConfig,
        "mapHistory": mapHistory or {},
        "metricsHistory": list(metricsHistory or [])[-500:],
        "optimizationState": optimizationState or {},
        "progressHistory": list(progressHistory or [])[-50:],
        "freshInit": freshInit,
        "timestamp": time.time(),
    }
    if optimizer is not None:
        payload["optimizer"] = optimizer.state_dict()
    if saveRng:
        payload["rngState"] = {
            "python": random.getstate(),
            "numpy": np.random.get_state(),
            "torch": torch.get_rng_state(),
        }

    tempPath = path.with_suffix(path.suffix + ".tmp")
    backupPath = path.with_suffix(path.suffix + ".bak")
    torch.save(payload, tempPath)
    if path.exists():
        try:
            shutil.copy2(path, backupPath)
        except OSError:
            pass
    tempPath.replace(path)
    return payload


def loadCheckpointFull(path, model, optimizer=None, restoreRng=False):
    """Load weights strictly. A missing checkpoint returns loaded=False; an
    incompatible checkpoint raises IncompatibleCheckpointError instead of
    silently loading mismatched weights."""
    path = Path(path)
    if not path.exists():
        return _emptyMeta()
    backupPath = path.with_suffix(path.suffix + ".bak")
    candidates = [path] + ([backupPath] if backupPath.exists() else [])
    lastError = None
    for candidate in candidates:
        try:
            payload = _readPayload(candidate)
        except Exception as error:
            lastError = error
            continue
        checkCompatibility(payload, model)
        model.load_state_dict(payload["model"])
        if optimizer is not None and "optimizer" in payload:
            try:
                optimizer.load_state_dict(payload["optimizer"])
            except Exception:
                pass
        if restoreRng and "rngState" in payload:
            rng = payload["rngState"]
            try:
                random.setstate(rng["python"])
                np.random.set_state(rng["numpy"])
                torch.set_rng_state(rng["torch"])
            except Exception:
                pass
        meta = _metaFromPayload(payload)
        meta["loadedFrom"] = str(candidate)
        return meta
    raise RuntimeError(f"Failed to read checkpoint {path}: {lastError}")


def loadCheckpoint(path, model, optimizer=None, restoreRng=False):
    meta = loadCheckpointFull(path, model, optimizer=optimizer, restoreRng=restoreRng)
    return int(meta["updates"]), float(meta["bestRate"])


def initializeFreshModel(path, model, seed=None, trainingConfig=None, reason="fresh"):
    """Write a brand-new randomly initialised model as version 0 of a new lineage."""
    pathObj = Path(path)
    if pathObj.exists():
        recoverable = pathObj.with_name(f"{pathObj.stem}_recoverable{pathObj.suffix}.bak")
        try:
            shutil.copy2(pathObj, recoverable)
        except OSError:
            pass
    modelId = uuid.uuid4().hex[:12]
    freshInit = {"timestamp": time.time(), "seed": seed, "reason": reason, "modelId": modelId}
    for suffix in (".bak", ".tmp"):
        stale = pathObj.with_suffix(pathObj.suffix + suffix)
        if stale.exists():
            stale.unlink()
    saveCheckpoint(
        path,
        model,
        updates=0,
        bestRate=0.0,
        version=0,
        modelId=modelId,
        trainingConfig=trainingConfig,
        freshInit=freshInit,
        saveRng=False,
    )
    return modelId, freshInit
