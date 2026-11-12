from .maze_environment import AuthoritativeMazeEnvironment


def replayActionTrace(mazeData, actionTrace, maxSteps=300, boneRewardValue=5):
    if not isinstance(actionTrace, list):
        return {
            "valid": False,
            "error": "Action trace must be a list",
        }
    if len(actionTrace) == 0:
        return {
            "valid": False,
            "error": "Action trace cannot be empty",
        }
    if len(actionTrace) > int(maxSteps):
        return {
            "valid": False,
            "error": f"Action trace length ({len(actionTrace)}) exceeds maxSteps ({maxSteps})",
        }

    try:
        env = AuthoritativeMazeEnvironment(
            mazeData,
            maxSteps=maxSteps,
            boneRewardValue=boneRewardValue,
        )
    except ValueError as exc:
        return {
            "valid": False,
            "error": f"Invalid competition maze: {exc}",
        }

    stepHistory = []
    for stepIdx, rawAction in enumerate(actionTrace):
        if env.done:
            return {
                "valid": False,
                "error": f"Action trace contains extra step at index {stepIdx} after episode terminated",
            }
        try:
            stepInfo = env.step(rawAction)
            stepHistory.append(stepInfo)
        except ValueError as exc:
            return {
                "valid": False,
                "error": f"Invalid action at step {stepIdx}: {exc}",
            }

    bonesCollected = len(env.bones) - len(env.remainingBones)
    verifiedScore = env.currentScore()
    return {
        "valid": True,
        "completed": bool(env.won),
        "timeout": bool(env.timeout),
        "done": bool(env.done),
        "steps": int(env.steps),
        "bones_collected": int(bonesCollected),
        "verified_score": int(verifiedScore),
        "final_position": [int(env.position[0]), int(env.position[1])],
        "normalized_actions": [s["action"] for s in stepHistory],
    }

