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
from ..services.ranking_service import getPlayerPositionsAndNearby, getPlayerTrophyHistory

router = APIRouter(prefix="/api/v1/players", tags=["players"])


@router.get("/me")
def getMyProfile(request, db):
    user = getCurrentUser(request, db=db)
    profRow = db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (user.id,))
    profile = PlayerProfileModel.fromRow(profRow)
    rankInfo = getPlayerPositionsAndNearby(db, user.id)
    return {
        "success": True,
        "player": formatPrivateProfile(
            user,
            profile,
            globalRank=rankInfo["global_position"],
            leagueRank=rankInfo["league_position"],
        ),
    }


@router.patch("/me")
def updateMyProfile(request, db):
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
    return {"success": True, "player": formatted}


@router.get("/me/rank")
def getMyRanking(request, db):
    user = getCurrentUser(request, db=db)
    radius = int(request.getQuery("radius", 2) or 2)
    rankInfo = getPlayerPositionsAndNearby(db, user.id, nearbyRadius=radius)
    return {"success": True, **rankInfo}


@router.get("/me/history")
def getMyHistory(request, db):
    user = getCurrentUser(request, db=db)
    limit = int(request.getQuery("limit", 25) or 25)
    offset = int(request.getQuery("offset", 0) or 0)
    matchHistory = getPlayerMatchHistory(db, user.id, limit=limit, offset=offset)
    trophyHistory = getPlayerTrophyHistory(db, user.id, limit=limit, offset=offset)
    return {
        "success": True,
        "player_id": user.id,
        "matches": matchHistory["matches"],
        "trophy_history": trophyHistory,
    }


@router.get("/me/trophies")
def getMyTrophyHistory(request, db):
    user = getCurrentUser(request, db=db)
    limit = int(request.getQuery("limit", 50) or 50)
    offset = int(request.getQuery("offset", 0) or 0)
    return {
        "success": True,
        "player_id": user.id,
        "trophy_history": getPlayerTrophyHistory(db, user.id, limit=limit, offset=offset),
    }


@router.get("/me/events")
def getMyMissedEvents(request, db):
    user = getCurrentUser(request, db=db)
    lastEventId = request.getQuery("last_event_id", None)
    sinceSeq = int(request.getQuery("since_seq", 0) or 0)
    events = wsManager.getMissedEvents(user.id, lastEventId=lastEventId, sinceSeq=sinceSeq, db=db)
    return {
        "success": True,
        "player_id": user.id,
        "count": len(events),
        "events": events,
    }


@router.get("/{username}")
def getPublicPlayerProfile(request, db):
    username = request.pathParams.get("username", "")
    userRow = db.fetchOne("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (str(username),))
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

