from ..core.exceptions import UnprocessableError


def validateProfileUpdateRequest(payload):
    if not isinstance(payload, dict):
        raise UnprocessableError("Request body must be a JSON object")
    out = {}
    if "display_name" in payload or "displayName" in payload:
        name = str(payload.get("display_name") or payload.get("displayName") or "").strip()
        if not name or len(name) > 36:
            raise UnprocessableError("Display name must be 1-36 characters")
        out["displayName"] = name
    if "avatar" in payload:
        avatar = str(payload.get("avatar") or "").strip()
        if not avatar or len(avatar) > 48:
            raise UnprocessableError("Invalid avatar identifier")
        out["avatar"] = avatar
    if "settings" in payload and isinstance(payload["settings"], dict):
        out["settings"] = payload["settings"]
    if "dog_model_version" in payload or "dogModelVersion" in payload:
        ver = payload.get("dog_model_version", payload.get("dogModelVersion"))
        out["dogModelVersion"] = max(1, int(ver))
    if "dog_model_info" in payload or "dogModelInfo" in payload:
        info = payload.get("dog_model_info") or payload.get("dogModelInfo")
        if isinstance(info, dict):
            out["dogModelInfo"] = info
    return out


def formatPublicProfile(user, profile, globalRank=None, leagueRank=None):
    return {
        "player_id": user.id,
        "username": user.username,
        "display_name": user.displayName,
        "avatar": user.avatar,
        "created_at": user.createdAt,
        "level": profile.level,
        "xp": profile.xp,
        "trophies": profile.trophies,
        "league": profile.league,
        "global_position": globalRank,
        "league_position": leagueRank,
        "wins": profile.wins,
        "losses": profile.losses,
        "draws": profile.draws,
        "win_rate": profile.winRate,
        "total_matches": profile.totalMatches,
        "best_score": profile.bestScore,
        "average_score": profile.averageScore,
        "total_bones_collected": profile.totalBonesCollected,
        "dog_model_version": profile.dogModelVersion,
        "dog_model_info": profile.dogModelInfo,
    }


def formatPrivateProfile(user, profile, globalRank=None, leagueRank=None):
    data = formatPublicProfile(user, profile, globalRank=globalRank, leagueRank=leagueRank)
    data.update({
        "email": user.email,
        "last_login": user.lastLogin,
        "updated_at": user.updatedAt,
        "settings": user.settings,
    })
    return data

