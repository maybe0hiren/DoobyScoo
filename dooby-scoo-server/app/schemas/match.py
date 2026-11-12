import uuid
from ..core.exceptions import UnprocessableError


def validateSubmissionPayload(payload, matchId, playerId):
    if not isinstance(payload, dict):
        raise UnprocessableError("Submission body must be a JSON object")

    actionTrace = payload.get("action_trace", payload.get("actionTrace"))
    if not isinstance(actionTrace, list):
        raise UnprocessableError("action_trace must be a list of actions")

    try:
        claimedScore = int(payload.get("claimed_score", payload.get("claimedScore")))
        claimedSteps = int(payload.get("claimed_steps", payload.get("steps", len(actionTrace))))
        claimedBones = int(payload.get("claimed_bones_collected", payload.get("bones_collected", payload.get("bonesCollected", 0))))
    except (TypeError, ValueError) as exc:
        raise UnprocessableError("claimed_score, claimed_steps, and claimed_bones_collected must be integers") from exc

    claimedCompletedRaw = payload.get("claimed_completed", payload.get("completed"))
    if claimedCompletedRaw is None:
        raise UnprocessableError("claimed_completed / completed boolean is required")
    claimedCompleted = bool(claimedCompletedRaw)

    finalPos = payload.get("final_position", payload.get("finalPosition", [0, 0]))
    if not isinstance(finalPos, (list, tuple)) or len(finalPos) != 2:
        raise UnprocessableError("final_position must be [x, y]")
    try:
        finalPosition = [int(finalPos[0]), int(finalPos[1])]
    except (TypeError, ValueError) as exc:
        raise UnprocessableError("final_position coordinates must be integers") from exc

    mapId = str(payload.get("map_id") or payload.get("mapId") or "").strip()
    mapHash = str(payload.get("map_hash") or payload.get("mapHash") or "").strip()
    submissionId = str(payload.get("submission_id") or payload.get("submissionId") or f"sub_{uuid.uuid4().hex[:16]}").strip()
    modelVersion = int(payload.get("model_version") or payload.get("modelVersion") or 1)

    return {
        "matchId": str(payload.get("match_id") or matchId),
        "playerId": str(payload.get("player_id") or playerId),
        "mapId": mapId,
        "mapHash": mapHash,
        "actionTrace": actionTrace,
        "claimedScore": claimedScore,
        "claimedSteps": claimedSteps,
        "claimedBones": claimedBones,
        "claimedCompleted": claimedCompleted,
        "finalPosition": finalPosition,
        "submissionId": submissionId,
        "modelVersion": modelVersion,
    }

