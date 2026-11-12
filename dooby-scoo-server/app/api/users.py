from ..core.dependencies import getCurrentUser
from ..core.exceptions import NotFoundError
from ..core.framework import APIRouter
from ..models.player_profile import PlayerProfileModel
from ..models.user import UserModel
from ..schemas.user import formatPublicProfile
from ..services.ranking_service import getPlayerPositionsAndNearby

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me")
def getCurrentUserAccount(request, db):
    user = getCurrentUser(request, db=db)
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
    }


@router.get("/{username}")
def getUserByUsername(request, db):
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

