from ..config import settings
from ..core.framework import APIRouter
from ..services.ranking_service import getGlobalLeaderboard, getLeagueLeaderboard

router = APIRouter(prefix="/api/v1/leaderboards", tags=["leaderboards"])


@router.get("/global")
def globalLeaderboardEndpoint(request, db):
    limit = int(request.getQuery("limit", 50) or 50)
    offset = int(request.getQuery("offset", 0) or 0)
    res = getGlobalLeaderboard(db, limit=limit, offset=offset)
    return {"success": True, **res}


@router.get("/leagues")
def listLeaguesEndpoint(request, db):
    return {
        "success": True,
        "leagues": [
            {"name": name, "min_trophies": minT, "max_trophies": maxT if maxT < 1000000 else None}
            for name, minT, maxT in settings.leagueThresholds
        ],
    }


@router.get("/league/{league}")
def leagueLeaderboardEndpoint(request, db):
    league = request.pathParams["league"]
    limit = int(request.getQuery("limit", 50) or 50)
    offset = int(request.getQuery("offset", 0) or 0)
    res = getLeagueLeaderboard(db, league, limit=limit, offset=offset)
    return {"success": True, **res}

