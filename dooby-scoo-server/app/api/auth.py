from ..core.dependencies import getCurrentUser
from ..core.framework import APIRouter
from ..schemas.user import formatPrivateProfile
from ..services.auth_service import (
    isUsernameAvailable,
    loginUser,
    logoutUser,
    refreshAccessToken,
    registerUser,
    resetPassword,
)
from ..services.ranking_service import getPlayerPositionsAndNearby

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=201)
def registerEndpoint(request, db):
    res = registerUser(db, request.body)
    rankInfo = getPlayerPositionsAndNearby(db, res["user"].id)
    return {
        "success": True,
        "access_token": res["accessToken"],
        "refresh_token": res["refreshToken"],
        "token_type": "bearer",
        "player": formatPrivateProfile(
            res["user"],
            res["profile"],
            globalRank=rankInfo["global_position"],
            leagueRank=rankInfo["league_position"],
        ),
    }


@router.post("/login")
def loginEndpoint(request, db):
    res = loginUser(db, request.body)
    rankInfo = getPlayerPositionsAndNearby(db, res["user"].id)
    return {
        "success": True,
        "access_token": res["accessToken"],
        "refresh_token": res["refreshToken"],
        "token_type": "bearer",
        "player": formatPrivateProfile(
            res["user"],
            res["profile"],
            globalRank=rankInfo["global_position"],
            leagueRank=rankInfo["league_position"],
        ),
    }


@router.post("/logout")
def logoutEndpoint(request, db):
    user = getCurrentUser(request, db=db)
    refreshToken = request.body.get("refresh_token") if isinstance(request.body, dict) else None
    return logoutUser(db, user.id, refreshToken=refreshToken)


@router.post("/refresh")
def refreshEndpoint(request, db):
    res = refreshAccessToken(db, request.body)
    return {
        "success": True,
        "access_token": res["accessToken"],
        "refresh_token": res["refreshToken"],
        "token_type": "bearer",
    }


@router.post("/password-reset")
def passwordResetEndpoint(request, db):
    return resetPassword(db, request.body)


@router.get("/username-available")
def usernameAvailableEndpoint(request, db):
    username = request.getQuery("username", "")
    available = isUsernameAvailable(db, username)
    return {
        "success": True,
        "username": str(username),
        "available": available,
    }

