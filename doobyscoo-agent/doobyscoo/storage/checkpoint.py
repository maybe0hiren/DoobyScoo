import random
import shutil
import time
from pathlib import Path
import numpy as np
import torch


def _readPayload(path):
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def getCheckpointMetadata(path):
    path = Path(path)
    target = path if path.exists() else path.with_suffix(path.suffix + ".bak")
    if not target.exists():
        return {
            "exists": False,
            "updates": 0,
            "version": 0,
            "totalEpisodes": 0,
            "totalSteps": 0,
            "bestRate": 0.0,
            "bestScore": None,
            "config": {},
        }
    try:
        payload = _readPayload(target)
        return {
            "exists": True,
            "updates": int(payload.get("updates", 0)),
            "version": int(payload.get("version", payload.get("updates", 1))),
            "totalEpisodes": int(payload.get("totalEpisodes", 0)),
            "totalSteps": int(payload.get("totalSteps", 0)),
            "bestRate": float(payload.get("bestRate", 0.0)),
            "bestScore": payload.get("bestScore", None),
            "config": payload.get("config", {}),
            "timestamp": payload.get("timestamp", None),
        }
    except Exception:
        return {
            "exists": False,
            "updates": 0,
            "version": 0,
            "totalEpisodes": 0,
            "totalSteps": 0,
            "bestRate": 0.0,
            "bestScore": None,
            "config": {},
        }


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
):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previousMeta = getCheckpointMetadata(path)
    if version is None:
        version = int(previousMeta.get("version", 0)) + 1
    if totalEpisodes == 0 and previousMeta.get("totalEpisodes", 0) > 0:
        totalEpisodes = int(previousMeta["totalEpisodes"])
    if totalSteps == 0 and previousMeta.get("totalSteps", 0) > 0:
        totalSteps = int(previousMeta["totalSteps"])
    if bestScore is None:
        bestScore = previousMeta.get("bestScore", None)

    modelConfig = {
        "observationSize": getattr(model, "observationSize", 8),
        "hiddenSize": getattr(model, "hiddenSize", 128),
    }
    if isinstance(config, dict):
        modelConfig.update(config)

    payload = {
        "model": model.state_dict(),
        "updates": int(updates),
        "version": int(version),
        "bestRate": float(bestRate),
        "bestScore": float(bestScore) if bestScore is not None else None,
        "totalEpisodes": int(totalEpisodes),
        "totalSteps": int(totalSteps),
        "config": modelConfig,
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
    path = Path(path)
    backupPath = path.with_suffix(path.suffix + ".bak")
    candidates = [p for p in (path, backupPath) if p.exists()]
    if not candidates:
        return {
            "loaded": False,
            "updates": 0,
            "version": 0,
            "bestRate": 0.0,
            "bestScore": None,
            "totalEpisodes": 0,
            "totalSteps": 0,
            "config": {},
        }

    lastError = None
    for candidate in candidates:
        try:
            payload = _readPayload(candidate)
            stateDict = payload["model"]
            currentDict = model.state_dict()
            shapeMismatch = any(
                k not in currentDict or currentDict[k].shape != v.shape for k, v in stateDict.items()
            )
            if shapeMismatch:
                compatible = {
                    k: v for k, v in stateDict.items() if k in currentDict and currentDict[k].shape == v.shape
                }
                currentDict.update(compatible)
                model.load_state_dict(currentDict, strict=False)
                return {
                    "loaded": False,
                    "updates": 0,
                    "version": 0,
                    "bestRate": 0.0,
                    "bestScore": None,
                    "totalEpisodes": 0,
                    "totalSteps": 0,
                    "config": payload.get("config", {}),
                }

            model.load_state_dict(stateDict)
            if optimizer is not None and "optimizer" in payload:
                try:
                    optimizer.load_state_dict(payload["optimizer"])
                except Exception:
                    pass
            if restoreRng and "rngState" in payload:
                rng = payload["rngState"]
                try:
                    if "python" in rng:
                        random.setstate(rng["python"])
                    if "numpy" in rng:
                        np.random.set_state(rng["numpy"])
                    if "torch" in rng:
                        torch.set_rng_state(rng["torch"])
                except Exception:
                    pass

            return {
                "loaded": True,
                "updates": int(payload.get("updates", 0)),
                "version": int(payload.get("version", payload.get("updates", 1))),
                "bestRate": float(payload.get("bestRate", 0.0)),
                "bestScore": payload.get("bestScore", None),
                "totalEpisodes": int(payload.get("totalEpisodes", 0)),
                "totalSteps": int(payload.get("totalSteps", 0)),
                "config": payload.get("config", {}),
            }
        except Exception as error:
            lastError = error
            continue

    raise RuntimeError(f"Failed to load checkpoint {path}: {lastError}")


def loadCheckpoint(path, model, optimizer=None, restoreRng=False):
    meta = loadCheckpointFull(path, model, optimizer=optimizer, restoreRng=restoreRng)
    return int(meta["updates"]), float(meta["bestRate"])

