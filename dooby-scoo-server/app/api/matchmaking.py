from ..core.dependencies import getCurrentUser
from ..core.framework import APIRouter
from ..services.matchmaking_service import (
    cancelMatchmaking,
    getMatchmakingStatus,
    joinMatchmaking,
)

router = APIRouter(prefix="/api/v1/matchmaking", tags=["matchmaking"])


@router.post("/join")
def joinMatchmakingEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    return joinMatchmaking(db, user.id)


@router.post("/cancel")
def cancelMatchmakingEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    return cancelMatchmaking(db, user.id)


@router.get("/status")
def matchmakingStatusEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    return getMatchmakingStatus(db, user.id, tryMatch=True)

