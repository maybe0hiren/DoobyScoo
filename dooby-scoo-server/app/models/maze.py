from dataclasses import dataclass
import json


@dataclass
class MazeMapModel:
    id: str
    version: int
    difficulty: str
    mazeJson: dict
    mazeHash: str
    createdAt: str

    @classmethod
    def fromRow(cls, row):
        if not row:
            return None
        rawJson = row.get("maze_json") or "{}"
        parsed = json.loads(rawJson) if isinstance(rawJson, str) else dict(rawJson)
        return cls(
            id=str(row["id"]),
            version=int(row.get("version", 1)),
            difficulty=str(row.get("difficulty") or "medium"),
            mazeJson=parsed,
            mazeHash=str(row["maze_hash"]),
            createdAt=str(row.get("created_at") or ""),
        )

