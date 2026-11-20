import json
from ..core.dependencies import getCurrentUser
from ..core.exceptions import NotFoundError
from ..core.framework import APIRouter
from ..core.security import nowIso
from ..core.websocket_manager import wsManager
from ..models.player_profile import PlayerProfileModel
from ..models.user import UserModel
from ..schemas.user import formatPrivateProfile, formatPublicProfile, validateProfileUpdateRequest
from ..services.match_service import getPlayerMatchHistory
from ..services.ranking_service import getPlayerPositionsAndNearby

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me")
def getCurrentUserAccount(request, db):
    user = getCurrentUser(request, db=db)
    profRow = db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (user.id,))
    profile = PlayerProfileModel.fromRow(profRow)
    rankInfo = getPlayerPositionsAndNearby(db, user.id)
    playerDict = formatPrivateProfile(
        user,
        profile,
        globalRank=rankInfo["global_position"],
        leagueRank=rankInfo["league_position"],
    )
    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.displayName,
            "avatar": user.avatar,
            "settings": user.settings,
            "created_at": user.createdAt,
            "updated_at": user.updatedAt,
            "last_login": user.lastLogin,
        },
        "player": playerDict,
    }


@router.patch("/me")
def updateCurrentUserAccount(request, db):
    user = getCurrentUser(request, db=db)
    updates = validateProfileUpdateRequest(request.body)
    now = nowIso()

    with db.transaction():
        if "displayName" in updates:
            db.execute("UPDATE users SET display_name = ?, updated_at = ? WHERE id = ?", (updates["displayName"], now, user.id))
        if "avatar" in updates:
            db.execute("UPDATE users SET avatar = ?, updated_at = ? WHERE id = ?", (updates["avatar"], now, user.id))
        if "settings" in updates:
            mergedSettings = dict(user.settings)
            mergedSettings.update(updates["settings"])
            db.execute("UPDATE users SET settings_json = ?, updated_at = ? WHERE id = ?", (json.dumps(mergedSettings), now, user.id))
        if "dogModelVersion" in updates:
            db.execute("UPDATE player_profiles SET dog_model_version = ? WHERE user_id = ?", (updates["dogModelVersion"], user.id))
        if "dogModelInfo" in updates:
            profRow = db.fetchOne("SELECT dog_model_info FROM player_profiles WHERE user_id = ?", (user.id,))
            currentInfo = json.loads(profRow["dog_model_info"]) if (profRow and profRow.get("dog_model_info")) else {}
            currentInfo.update(updates["dogModelInfo"])
            db.execute("UPDATE player_profiles SET dog_model_info = ? WHERE user_id = ?", (json.dumps(currentInfo), user.id))

    freshUser = UserModel.fromRow(db.fetchOne("SELECT * FROM users WHERE id = ?", (user.id,)))
    freshProf = PlayerProfileModel.fromRow(db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (user.id,)))
    rankInfo = getPlayerPositionsAndNearby(db, user.id)
    formatted = formatPrivateProfile(
        freshUser,
        freshProf,
        globalRank=rankInfo["global_position"],
        leagueRank=rankInfo["league_position"],
    )
    wsManager.emitEvent(
        "player.profile_updated",
        {"player_id": user.id, "display_name": freshUser.displayName, "avatar": freshUser.avatar},
        userId=user.id,
        db=db,
    )
    return {
        "success": True,
        "user": {
            "id": freshUser.id,
            "username": freshUser.username,
            "email": freshUser.email,
            "display_name": freshUser.displayName,
            "avatar": freshUser.avatar,
            "settings": freshUser.settings,
            "created_at": freshUser.createdAt,
            "updated_at": freshUser.updatedAt,
            "last_login": freshUser.lastLogin,
        },
        "player": formatted,
    }


@router.get("/{user_id}/stats")
def getUserStatsEndpoint(request, db):
    identifier = request.pathParams.get("user_id", "")
    userRow = db.fetchOne(
        "SELECT * FROM users WHERE id = ? OR LOWER(username) = LOWER(?)",
        (str(identifier), str(identifier)),
    )
    if not userRow:
        raise NotFoundError("Player not found")
    user = UserModel.fromRow(userRow)
    profRow = db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (user.id,))
    profile = PlayerProfileModel.fromRow(profRow)
    rankInfo = getPlayerPositionsAndNearby(db, user.id)
    history = getPlayerMatchHistory(db, user.id, limit=10, offset=0)
    pub = formatPublicProfile(
        user,
        profile,
        globalRank=rankInfo["global_position"],
        leagueRank=rankInfo["league_position"],
    )
    return {
        "success": True,
        "stats": pub,
        "player": pub,
        "recent_battles": history["matches"],
    }


@router.get("/{username}")
def getUserByUsername(request, db):
    username = request.pathParams.get("username", "")
    userRow = db.fetchOne(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR id = ?",
        (str(username), str(username)),
    )
    if not userRow:
        raise NotFoundError("Player not found")
    user = UserModel.fromRow(userRow)
    profRow = db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (user.id,))
    profile = PlayerProfileModel.fromRow(profRow)
    rankInfo = getPlayerPositionsAndNearby(db, user.id)
    return {
        "success": True,
        "player": formatPublicProfile(
            user,
            profile,
            globalRank=rankInfo["global_position"],
            leagueRank=rankInfo["league_position"],
        ),
    }

