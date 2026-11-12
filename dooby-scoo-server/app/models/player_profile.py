from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class PlayerProfileModel:
    userId: str
    level: int = 1
    xp: int = 0
    trophies: int = 0
    league: str = "Beginner"
    wins: int = 0
    losses: int = 0
    draws: int = 0
    bestScore: Optional[int] = None
    averageScore: Optional[float] = None
    totalMatches: int = 0
    totalBonesCollected: int = 0
    dogModelVersion: int = 1
    dogModelInfo: dict = field(default_factory=dict)

    @property
    def winRate(self):
        if self.totalMatches <= 0:
            return 0.0
        return round(float(self.wins) / float(self.totalMatches), 4)

    @classmethod
    def fromRow(cls, row):
        if not row:
            return None
        infoRaw = row.get("dog_model_info") or "{}"
        try:
            dogInfo = json.loads(infoRaw) if isinstance(infoRaw, str) else dict(infoRaw)
        except Exception:
            dogInfo = {}
        return cls(
            userId=str(row["user_id"]),
            level=int(row.get("level", 1)),
            xp=int(row.get("xp", 0)),
            trophies=int(row.get("trophies", 0)),
            league=str(row.get("league") or "Beginner"),
            wins=int(row.get("wins", 0)),
            losses=int(row.get("losses", 0)),
            draws=int(row.get("draws", 0)),
            bestScore=int(row["best_score"]) if row.get("best_score") is not None else None,
            averageScore=round(float(row["average_score"]), 2) if row.get("average_score") is not None else None,
            totalMatches=int(row.get("total_matches", 0)),
            totalBonesCollected=int(row.get("total_bones_collected", 0)),
            dogModelVersion=int(row.get("dog_model_version", 1)),
            dogModelInfo=dogInfo,
        )

