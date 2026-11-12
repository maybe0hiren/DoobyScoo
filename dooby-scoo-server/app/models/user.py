from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class UserModel:
    id: str
    username: str
    email: str
    passwordHash: str
    displayName: str
    avatar: str = "dog_default"
    settings: dict = field(default_factory=dict)
    createdAt: str = ""
    updatedAt: str = ""
    lastLogin: Optional[str] = None

    @classmethod
    def fromRow(cls, row):
        if not row:
            return None
        settingsRaw = row.get("settings_json") or "{}"
        try:
            parsedSettings = json.loads(settingsRaw) if isinstance(settingsRaw, str) else dict(settingsRaw)
        except Exception:
            parsedSettings = {}
        return cls(
            id=str(row["id"]),
            username=str(row["username"]),
            email=str(row["email"]),
            passwordHash=str(row["password_hash"]),
            displayName=str(row["display_name"]),
            avatar=str(row.get("avatar") or "dog_default"),
            settings=parsedSettings,
            createdAt=str(row.get("created_at") or ""),
            updatedAt=str(row.get("updated_at") or ""),
            lastLogin=row.get("last_login"),
        )

