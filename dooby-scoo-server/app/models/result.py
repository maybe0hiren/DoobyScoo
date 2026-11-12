from dataclasses import dataclass
import json


@dataclass
class MatchResultModel:
    id: str
    submissionId: str
    matchId: str
    playerId: str
    actionTrace: list
    claimedScore: int
    verifiedScore: int
    steps: int
    bonesCollected: int
    completed: bool
    finalPosition: list
    modelVersion: int
    verificationStatus: str
    submittedAt: str

    @classmethod
    def fromRow(cls, row):
        if not row:
            return None
        rawTrace = row.get("action_trace") or "[]"
        trace = json.loads(rawTrace) if isinstance(rawTrace, str) else list(rawTrace)
        rawPos = row.get("final_position") or "[0, 0]"
        pos = json.loads(rawPos) if isinstance(rawPos, str) else list(rawPos)
        return cls(
            id=str(row["id"]),
            submissionId=str(row["submission_id"]),
            matchId=str(row["match_id"]),
            playerId=str(row["player_id"]),
            actionTrace=trace,
            claimedScore=int(row["claimed_score"]),
            verifiedScore=int(row["verified_score"]),
            steps=int(row["steps"]),
            bonesCollected=int(row["bones_collected"]),
            completed=bool(int(row["completed"])),
            finalPosition=pos,
            modelVersion=int(row.get("model_version", 1)),
            verificationStatus=str(row["verification_status"]),
            submittedAt=str(row.get("submitted_at") or ""),
        )

