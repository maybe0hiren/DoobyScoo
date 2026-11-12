from ..core.dependencies import getCurrentUser
from ..core.framework import APIRouter
from ..services.match_service import (
    formatMatchDetails,
    getMatchMapPayload,
    getPlayerMatchHistory,
    submitMatchResult,
)

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


@router.get("/history")
def getMatchesHistoryEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    limit = int(request.getQuery("limit", 25) or 25)
    offset = int(request.getQuery("offset", 0) or 0)
    res = getPlayerMatchHistory(db, user.id, limit=limit, offset=offset)
    return {"success": True, **res}


@router.get("/{match_id}")
def getMatchEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    matchId = request.pathParams["match_id"]
    return formatMatchDetails(db, matchId, requestingPlayerId=user.id)


@router.get("/{match_id}/map")
def getMatchMapEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    matchId = request.pathParams["match_id"]
    payload = getMatchMapPayload(db, matchId, user.id)
    return {"success": True, **payload}


@router.post("/{match_id}/submit")
def submitMatchEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    matchId = request.pathParams["match_id"]
    return submitMatchResult(db, matchId, user.id, request.body)


@router.get("/{match_id}/result")
def getMatchResultEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    matchId = request.pathParams["match_id"]
    return formatMatchDetails(db, matchId, requestingPlayerId=user.id)

