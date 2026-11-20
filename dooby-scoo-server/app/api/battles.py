from ..core.dependencies import getCurrentUser
from ..core.framework import APIRouter
from ..services.match_service import (
    formatMatchDetails,
    getMatchMapPayload,
    getPlayerMatchHistory,
    submitMatchResult,
)

router = APIRouter(prefix="/api/v1/battles", tags=["battles"])


@router.get("/history")
def getBattlesHistoryEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    limit = int(request.getQuery("limit", 25) or 25)
    offset = int(request.getQuery("offset", 0) or 0)
    res = getPlayerMatchHistory(db, user.id, limit=limit, offset=offset)
    return {"success": True, "battles": res["matches"], **res}


@router.get("/{battle_id}")
def getBattleEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    battleId = request.pathParams["battle_id"]
    details = formatMatchDetails(db, battleId, requestingPlayerId=user.id)
    details["battle_id"] = details["match_id"]
    return details


@router.get("/{battle_id}/map")
def getBattleMapEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    battleId = request.pathParams["battle_id"]
    payload = getMatchMapPayload(db, battleId, user.id)
    payload["battle_id"] = payload["match_id"]
    return {"success": True, **payload}


@router.post("/{battle_id}/actions")
def submitBattleActionsEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    battleId = request.pathParams["battle_id"]
    res = submitMatchResult(db, battleId, user.id, request.body)
    res["battle_id"] = res["match_id"]
    return res


@router.post("/{battle_id}/submit")
def submitBattleResultEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    battleId = request.pathParams["battle_id"]
    res = submitMatchResult(db, battleId, user.id, request.body)
    res["battle_id"] = res["match_id"]
    return res


@router.get("/{battle_id}/result")
def getBattleResultEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    battleId = request.pathParams["battle_id"]
    details = formatMatchDetails(db, battleId, requestingPlayerId=user.id)
    details["battle_id"] = details["match_id"]
    return details

