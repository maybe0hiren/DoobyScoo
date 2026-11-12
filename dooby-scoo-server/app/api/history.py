from ..core.dependencies import getCurrentUser
from ..core.framework import APIRouter
from ..services.match_service import getPlayerMatchHistory
from ..services.ranking_service import getPlayerTrophyHistory

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("/matches")
def matchHistoryEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    limit = int(request.getQuery("limit", 25) or 25)
    offset = int(request.getQuery("offset", 0) or 0)
    res = getPlayerMatchHistory(db, user.id, limit=limit, offset=offset)
    return {"success": True, **res}


@router.get("/trophies")
def trophyHistoryEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    limit = int(request.getQuery("limit", 50) or 50)
    offset = int(request.getQuery("offset", 0) or 0)
    return {
        "success": True,
        "player_id": user.id,
        "trophy_history": getPlayerTrophyHistory(db, user.id, limit=limit, offset=offset),
    }

