from dataclasses import dataclass


@dataclass
class TrophyHistoryModel:
    id: str
    playerId: str
    matchId: str
    previousTrophies: int
    trophyChange: int
    newTrophies: int
    createdAt: str

    @classmethod
    def fromRow(cls, row):
        if not row:
            return None
        return cls(
            id=str(row["id"]),
            playerId=str(row["player_id"]),
            matchId=str(row["match_id"]),
            previousTrophies=int(row["previous_trophies"]),
            trophyChange=int(row["trophy_change"]),
            newTrophies=int(row["new_trophies"]),
            createdAt=str(row.get("created_at") or ""),
        )

