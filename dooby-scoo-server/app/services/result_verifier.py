from ..config import settings
from ..core.exceptions import BadRequestError
from ..rl_verification.action_replay import replayActionTrace


def verifyPlayerSubmission(matchModel, mapModel, submissionData):
    if submissionData.get("mapId") and submissionData["mapId"] != matchModel.mapId:
        raise BadRequestError("Submitted map_id does not match assigned match map", code="map_mismatch")
    if submissionData.get("mapHash") and submissionData["mapHash"] != matchModel.mapHash:
        raise BadRequestError("Submitted map_hash does not match assigned match map hash", code="map_hash_mismatch")

    maxSteps = int(matchModel.rules.get("max_steps", settings.maxMatchSteps))
    boneRewardValue = int(matchModel.rules.get("bone_reward_value", 5))

    replay = replayActionTrace(
        mapModel.mazeJson,
        submissionData["actionTrace"],
        maxSteps=maxSteps,
        boneRewardValue=boneRewardValue,
    )
    if not replay["valid"]:
        raise BadRequestError(replay["error"], code="invalid_action_trace")

    if int(submissionData["claimedSteps"]) != int(replay["steps"]):
        raise BadRequestError(
            f"Claimed steps ({submissionData['claimedSteps']}) do not match replayed steps ({replay['steps']})",
            code="steps_mismatch",
        )
    if int(submissionData["claimedBones"]) != int(replay["bones_collected"]):
        raise BadRequestError(
            f"Claimed bones_collected ({submissionData['claimedBones']}) do not match replayed bones ({replay['bones_collected']})",
            code="bones_mismatch",
        )
    if bool(submissionData["claimedCompleted"]) != bool(replay["completed"]):
        raise BadRequestError(
            f"Claimed completion ({submissionData['claimedCompleted']}) does not match replayed completion ({replay['completed']})",
            code="completion_mismatch",
        )
    if int(submissionData["claimedScore"]) != int(replay["verified_score"]):
        raise BadRequestError(
            f"Claimed score ({submissionData['claimedScore']}) does not match verified score ({replay['verified_score']})",
            code="score_mismatch",
        )
    if "finalPosition" in submissionData and submissionData["finalPosition"] is not None:
        if list(submissionData["finalPosition"]) != list(replay["final_position"]):
            raise BadRequestError(
                f"Claimed final_position {submissionData['finalPosition']} does not match replayed position {replay['final_position']}",
                code="position_mismatch",
            )

    return {
        "verified": True,
        "verifiedScore": int(replay["verified_score"]),
        "steps": int(replay["steps"]),
        "bonesCollected": int(replay["bones_collected"]),
        "completed": bool(replay["completed"]),
        "timeout": bool(replay["timeout"]),
        "finalPosition": replay["final_position"],
        "normalizedActions": replay["normalized_actions"],
    }


def determineMatchWinner(player1Id, res1, player2Id, res2, allowDraw=True):
    p1 = str(player1Id)
    p2 = str(player2Id)

    if res1 is not None and res2 is None:
        return {"winnerId": p1, "isDraw": False, "reason": "opponent_forfeit_or_timeout"}
    if res2 is not None and res1 is None:
        return {"winnerId": p2, "isDraw": False, "reason": "opponent_forfeit_or_timeout"}
    if res1 is None and res2 is None:
        return {"winnerId": None, "isDraw": True, "reason": "no_submissions"}

    c1 = bool(res1.completed)
    c2 = bool(res2.completed)

    if c1 and not c2:
        return {"winnerId": p1, "isDraw": False, "reason": "completion_advantage"}
    if c2 and not c1:
        return {"winnerId": p2, "isDraw": False, "reason": "completion_advantage"}

    if not c1 and not c2:
        if allowDraw:
            return {"winnerId": None, "isDraw": True, "reason": "both_failed"}
        key1 = (int(res1.verifiedScore), int(res1.steps), str(res1.submittedAt), p1)
        key2 = (int(res2.verifiedScore), int(res2.steps), str(res2.submittedAt), p2)
        return {"winnerId": p1 if key1 <= key2 else p2, "isDraw": False, "reason": "tie_break_both_failed"}

    if int(res1.verifiedScore) < int(res2.verifiedScore):
        return {"winnerId": p1, "isDraw": False, "reason": "lower_score"}
    if int(res2.verifiedScore) < int(res1.verifiedScore):
        return {"winnerId": p2, "isDraw": False, "reason": "lower_score"}

    if int(res1.steps) < int(res2.steps):
        return {"winnerId": p1, "isDraw": False, "reason": "fewer_steps"}
    if int(res2.steps) < int(res1.steps):
        return {"winnerId": p2, "isDraw": False, "reason": "fewer_steps"}

    if allowDraw:
        return {"winnerId": None, "isDraw": True, "reason": "equal_score_and_steps"}

    tieKey1 = (str(res1.submittedAt), p1)
    tieKey2 = (str(res2.submittedAt), p2)
    return {
        "winnerId": p1 if tieKey1 <= tieKey2 else p2,
        "isDraw": False,
        "reason": "deterministic_tie_break",
    }

