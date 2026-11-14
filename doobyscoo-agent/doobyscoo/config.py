"""Centralized, serializable training configuration for the DoobyScoo RL agent.

Every reward, score limit, revisit penalty, bone reward, exploration, PPO, rehearsal
and sampling knob lives here so that no value is hardcoded across modules.
Official multiplayer scoring (Official Score = Steps - 5 * Bones Collected) is
completely separate and never altered by training configuration.
"""
import copy
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "reward": {
        "maxScoreLimit": 100.0,            # training episode terminates immediately when trainingScore > 100
        "stepScoreCost": 1.0,              # each step adds +1 to training score
        "boneScoreReduction": -10.0,       # Bones 1..4 each reduce training score by -10
        "fifthBoneScoreReduction": -20.0,  # 5th Bone reduces training score by -20 (total -60 for all 5)
        "movePenalty": -0.5,               # ordinary movement step cost in RL reward
        "boneReward": 10.0,                # RL reward for each of the first 4 Bones
        "fifthBoneReward": 20.0,           # RL reward for the 5th Bone (double ordinary bone; total +60)
        "allBonesBonus": 10.0,             # extra bonus added on the 5th Bone (boneReward + allBonesBonus = 20)
        "endReward": 25.0,                 # reaching an End
        "wallPenalty": -12.0,              # wall / boundary collision (strictly worse than max revisit -8)
        "firstVisitPenalty": 0.0,          # 1st visit to a cell has 0 revisit penalty
        "revisitPenalty": -2.0,            # 2nd visit penalty (-2)
        "repeatedRevisitPenalty": -2.0,    # extra penalty per subsequent visit (3rd=-4, 4th=-6, 5th+=-8)
        "maxRevisitPenalty": -8.0,         # cap on revisit penalty (-8) so backtracking remains possible
        "noveltyReward": 1.5,              # intrinsic reward for visiting an unexplored cell for the first time
        "deadEndPenalty": -2.5,            # penalty for re-entering a previously identified dead end
        "loopPenalty": -1.5,               # penalty for repeating a movement oscillation or corridor loop
        "progressReward": 0.4,             # shaping bonus for moving toward active objective on revisited cells
        "regressPenalty": -0.3,            # shaping penalty for moving away from active objective without novelty
        "scoreLimitPenalty": -15.0,        # negative terminal reward when trainingScore > maxScoreLimit
        "stepLimitPenalty": -10.0,         # negative terminal reward when steps >= maxSteps
        "failurePenalty": -10.0,           # terminal failure penalty when episode ends without reaching End
    },
    "exploration": {
        "entropyStart": 0.028,
        "entropyEnd": 0.008,
        "entropyDecayUpdates": 250,
        "entropyTarget": 0.35,
        "entropyBoost": 2.0,
        "noveltyAnnealUpdates": 0,
        "noveltyFloor": 0.5,
        "routeDiversityBonus": 0.55,       # exploratory preference for unvisited alternative corridors at junctions
        "deadEndAvoidanceBias": 2.5,       # logit suppression for known empty dead-end branches when alternatives exist
    },
    "ppo": {
        "learningRate": 8e-4,
        "gamma": 0.99,
        "gaeLambda": 0.95,
        "shortGamma": 0.50,
        "shortLambda": 0.50,
        "shortAdvantageWeight": 0.55,
        "clipRange": 0.2,
        "valueCoef": 0.5,
        "maxGradNorm": 0.5,
        "epochs": 4,
        "minibatchEpisodes": 8,
        "targetKl": 0.04,
        "hiddenSize": 128,
        "rewardScale": 0.1,                # internal GAE/critic scaling for [-12, +25] step rewards
    },
    "training": {
        "episodesPerUpdate": 16,
        "attemptsPerMaze": 2,              # repeated attempts per sampled maze during training
        "maxSteps": 300,
        "maxScoreLimit": 100,
        "evalInterval": 10,
        "evalEpisodesPerMap": 1,
        "cpuThreads": 4,
        "seed": None,
    },
    "sampling": {
        "strategy": "shuffled_deck",
        "struggleFraction": 0.25,
        "uniqueMapsPerBatch": True,
    },
    "rehearsal": {
        "probability": 0.35,
        "maxProbability": 0.6,
        "adaptive": True,
        "retentionTolerance": 0.10,
        "retentionSampleSize": 12,
        "playedRatio": 0.4,
    },
    "continual": {
        "updates": 3,
        "episodesPerUpdate": 8,
        "newMapEpisodes": 4,
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
    cfg = _deepMerge(defaultConfig(), override or {})
    if override and "training" in override and "maxScoreLimit" in override["training"]:
        if not ("reward" in override and "maxScoreLimit" in override["reward"]):
            cfg["reward"]["maxScoreLimit"] = float(override["training"]["maxScoreLimit"])
    return cfg


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
