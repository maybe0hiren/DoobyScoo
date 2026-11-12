from dataclasses import dataclass, field
from typing import Optional
import json

MATCH_STATES = (
    "SEARCHING",
    "OPPONENT_FOUND",
    "MATCH_CREATED",
    "MAP_ASSIGNED",
    "AWAITING_RESULTS",
    "VERIFYING",
    "COMPLETED",
    "CANCELLED",
    "EXPIRED",
)


@dataclass
class MatchModel:
    id: str
    player1Id: str
    player2Id: str
    mapId: str
    mapVersion: int
    mapHash: str
    rules: dict = field(default_factory=dict)
    status: str = "AWAITING_RESULTS"
    verificationStatus: str = "PENDING"
    winnerId: Optional[str] = None
    createdAt: str = ""
    startedAt: str = ""
    expiresAt: str = ""
    completedAt: Optional[str] = None

    @classmethod
    def fromRow(cls, row):
        if not row:
            return None
        rulesRaw = row.get("rules_json") or "{}"
        try:
            rules = json.loads(rulesRaw) if isinstance(rulesRaw, str) else dict(rulesRaw)
        except Exception:
            rules = {}
        return cls(
            id=str(row["id"]),
            player1Id=str(row["player_1_id"]),
            player2Id=str(row["player_2_id"]),
            mapId=str(row["map_id"]),
            mapVersion=int(row.get("map_version", 1)),
            mapHash=str(row["map_hash"]),
            rules=rules,
            status=str(row["status"]),
            verificationStatus=str(row.get("verification_status") or "PENDING"),
            winnerId=row.get("winner_id"),
            createdAt=str(row.get("created_at") or ""),
            startedAt=str(row.get("started_at") or ""),
            expiresAt=str(row.get("expires_at") or ""),
            completedAt=row.get("completed_at"),
        )

