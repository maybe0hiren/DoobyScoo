"""Centralized, serializable configuration for the rebuilt DoobyScoo RL agent.

Designed around the true DoobyScoo objective:
    Official Score = Steps - (5 * Bones Collected)  (Lower score wins)

Every step costs -1.0 in RL reward. Wandering/novelty rewards are 0.0 so the
agent never wanders aimlessly for exploration points. Revisits, immediate
reversals, repeated edge traversals, oscillation loops, and dead-end re-entries
carry escalating penalties, while Bone collection and reaching the End provide
strong score-aligned rewards.
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
        "movePenalty": -1.0,               # every movement step costs -1.0
        "boneReward": 12.0,                # RL reward for each of the first 4 Bones (+12.0 >> 1.0 step cost)
        "fifthBoneReward": 24.0,           # RL reward for the 5th Bone (double ordinary bone; total +72)
        "allBonesBonus": 12.0,             # extra bonus added on the 5th Bone
        "endReward": 35.0,                 # reaching an End (+35.0 primary objective)
        "efficiencyBonusScale": 15.0,      # additional score-aware bonus at End for low official score
        "wallPenalty": -12.0,              # wall / boundary collision
        "firstVisitPenalty": 0.0,          # 1st visit to a cell has 0 revisit penalty (only movePenalty -1.0)
        "revisitPenalty": -2.5,            # 2nd visit penalty (-2.5)
        "repeatedRevisitPenalty": -2.5,    # extra penalty per subsequent visit (3rd=-5.0, 4th=-7.5, 5th+=-10.0)
        "maxRevisitPenalty": -10.0,        # cap on cell revisit penalty (-10.0)
        "recentRevisitPenalty": -1.5,      # extra penalty for returning to a cell visited within the last 4 steps
        "edgeRepeatPenalty": -1.5,         # extra penalty per prior traversal of the exact same directed doorway
        "reversePenalty": -2.0,            # penalty for immediate A->B->A reversal when non-dead-end alternatives exist
        "oscillationPenalty": -6.0,        # severe penalty for 2-block (A-B-A-B) or 3-block cycle oscillation
        "deadEndPenalty": -4.5,            # penalty for re-entering a known empty dead-end cell or branch
        "loopPenalty": -3.5,               # penalty for repeating a corridor loop
        "noveltyReward": 0.0,              # ZERO wandering bonus: visiting new cells is only a means to objectives
        "progressReward": 0.45,            # shaping bonus for moving closer to the locked objective
        "regressPenalty": -0.55,           # shaping penalty for moving away from the locked objective without reason
        "scoreLimitPenalty": -18.0,        # negative terminal reward when trainingScore > maxScoreLimit
        "stepLimitPenalty": -15.0,         # negative terminal reward when steps >= maxSteps
        "failurePenalty": -12.0,           # terminal failure penalty when episode ends without reaching End
    },
    "navigation": {
        "maxDetourStepsPerBone": 7,        # a Bone is worth 5 official score points; avoid long detours > ~7 steps
        "hysteresisMargin": 2,             # target-lock hysteresis so the Dog does not flip-flop objectives
        "maxStallStepsOnTarget": 6,        # abandon a blocked/unreachable Bone target after 6 non-progress steps
        "oscillationShieldBias": 9.0,      # action-selection logit suppression against active oscillation loops
        "deadEndAvoidanceBias": 7.5,       # action-selection logit suppression against known empty dead ends
        "revisitAvoidanceScale": 2.4,      # per-visit logit penalty on already-visited neighbors
        "edgeRepeatAvoidanceScale": 2.6,   # per-traversal logit penalty on already-traversed directed doorways
        "unexploredFrontierBonus": 2.2,    # preference for unexplored viable exits at junctions
        "objectivePullScale": 3.2,         # directional preference toward the locked score-optimal objective
    },
    "exploration": {
        "entropyStart": 0.024,
        "entropyEnd": 0.006,
        "entropyDecayUpdates": 200,
        "entropyTarget": 0.30,
        "entropyBoost": 1.8,
        "noveltyAnnealUpdates": 0,
        "noveltyFloor": 0.0,
        "routeDiversityBonus": 0.65,
        "deadEndAvoidanceBias": 7.5,
    },
    "ppo": {
        "learningRate": 8e-4,
        "gamma": 0.99,
        "gaeLambda": 0.95,
        "shortGamma": 0.55,
        "shortLambda": 0.55,
        "shortAdvantageWeight": 0.55,
        "clipRange": 0.2,
        "valueCoef": 0.5,
        "maxGradNorm": 0.5,
        "epochs": 4,
        "minibatchEpisodes": 8,
        "targetKl": 0.04,
        "hiddenSize": 128,
        "rewardScale": 0.1,
    },
    "training": {
        "episodesPerUpdate": 16,
        "attemptsPerMaze": 2,
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
        scale = 1.0 - frac * (1.0 - float(exp.get("noveltyFloor", 0.0)))
        reward["noveltyReward"] = float(reward["noveltyReward"]) * scale
    return reward

