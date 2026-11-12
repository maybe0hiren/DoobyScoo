"""Centralized, serializable training configuration for the DoobyScoo RL agent.

Every reward, exploration, PPO, rehearsal and sampling knob lives here so that no
value is hardcoded across modules. Configs are stored inside checkpoints and can
be loaded from / written to JSON (see config/training_config.json).
"""
import copy
import json
from pathlib import Path

DEFAULT_CONFIG = {
    # RL training reward (shaping). Completely separate from the official score
    # (Official Score = Steps - 5 * Bones Collected), which is never changed here.
    "reward": {
        "movePenalty": -0.04,            # every step taken (ordinary movement cost)
        "boneReward": 3.5,               # once per bone (~88x the movement cost)
        "allBonesBonus": 2.0,            # extra once when the last bone is collected
        "endReward": 10.0,               # reaching an End
        "wallPenalty": -0.60,            # bumping into a wall / boundary (always worse than backtracking)
        "revisitPenalty": -0.08,         # entering a square visited once before
        "repeatedRevisitPenalty": -0.04, # extra penalty per additional prior visit
        "maxRevisitPenalty": -0.24,      # cap so necessary backtracking stays affordable
        "noveltyReward": 0.08,           # intrinsic: first visit to a square this episode
        "stepLimitPenalty": -2.0,        # episode hit maxSteps
        "failurePenalty": -3.0,          # episode ended without reaching an End
    },
    "exploration": {
        "entropyStart": 0.025,           # entropy coefficient at update 0
        "entropyEnd": 0.006,             # entropy coefficient after entropyDecayUpdates
        "entropyDecayUpdates": 250,      # linear schedule length
        "entropyTarget": 0.30,           # nats; if policy entropy falls below, boost coefficient
        "entropyBoost": 2.0,             # multiplier applied while below target
        "noveltyAnnealUpdates": 0,       # 0 = constant novelty; >0 linearly anneals novelty to noveltyFloor
        "noveltyFloor": 0.5,             # fraction of noveltyReward kept after annealing
    },
    "ppo": {
        "learningRate": 8e-4,
        "gamma": 0.99,
        "gaeLambda": 0.95,
        "shortGamma": 0.50,              # short-horizon GAE for low-variance local credit assignment
        "shortLambda": 0.50,
        "shortAdvantageWeight": 0.55,    # blend weight between short- and long-horizon GAE
        "clipRange": 0.2,
        "valueCoef": 0.5,
        "maxGradNorm": 0.5,
        "epochs": 4,
        "minibatchEpisodes": 8,
        "targetKl": 0.04,                # early-stop epochs when approx KL exceeds 1.5 * targetKl
        "hiddenSize": 128,
    },
    "training": {
        "episodesPerUpdate": 16,
        "maxSteps": 300,
        "evalInterval": 10,
        "evalEpisodesPerMap": 1,
        "cpuThreads": 4,
        "seed": None,
    },
    "sampling": {
        "strategy": "shuffled_deck",     # every map is visited once per deck pass, in random order
        "struggleFraction": 0.25,        # share of each batch reserved for low-win-rate maps
        "uniqueMapsPerBatch": True,      # avoid duplicate maps inside one batch when possible
    },
    "rehearsal": {
        "probability": 0.35,             # share of each batch drawn from previously learned maps
        "maxProbability": 0.6,           # adaptive upper bound
        "adaptive": True,                # raise rehearsal when old-map performance drops
        "retentionTolerance": 0.10,      # allowed drop in retention win rate before raising rehearsal
        "retentionSampleSize": 12,       # old maps evaluated each eval interval
        "playedRatio": 0.4,              # share of rehearsal drawn from maps/played (continual learning)
    },
    "continual": {
        "updates": 3,
        "episodesPerUpdate": 8,
        "newMapEpisodes": 4,             # fresh on-policy rollouts on newly played maps per update
        "learningRate": 3e-4,
    },
}


def _deepMerge(base, override):
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deepMerge(base[key], value)
        else:
            base[key] = value
    return base


def defaultConfig():
    return copy.deepcopy(DEFAULT_CONFIG)


def makeConfig(override=None):
    return _deepMerge(defaultConfig(), override or {})


def loadConfig(path=None):
    if path is None:
        return defaultConfig()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return makeConfig(data)


def saveConfig(config, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def entropyCoefficient(config, updateNumber, measuredEntropy=None):
    exp = config["exploration"]
    span = max(1, int(exp["entropyDecayUpdates"]))
    frac = min(1.0, max(0.0, float(updateNumber) / span))
    coef = float(exp["entropyStart"]) + frac * (float(exp["entropyEnd"]) - float(exp["entropyStart"]))
    if measuredEntropy is not None and measuredEntropy < float(exp["entropyTarget"]):
        coef *= float(exp["entropyBoost"])
    return coef


def rewardConfigForUpdate(config, updateNumber):
    reward = dict(config["reward"])
    exp = config["exploration"]
    annealSpan = int(exp.get("noveltyAnnealUpdates", 0))
    if annealSpan > 0:
        frac = min(1.0, float(updateNumber) / annealSpan)
        scale = 1.0 - frac * (1.0 - float(exp.get("noveltyFloor", 0.5)))
        reward["noveltyReward"] = float(reward["noveltyReward"]) * scale
    return reward
