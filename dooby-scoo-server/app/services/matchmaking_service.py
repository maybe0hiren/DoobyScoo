import time
from ..config import settings
from ..core.exceptions import NotFoundError
from ..core.websocket_manager import wsManager
from .match_service import checkAndExpireMatch, createMatchForPlayers, formatMatchDetails


def _cleanupExpiredQueueEntries(db):
    nowTs = time.time()
    expiredRows = db.fetchAll(
        "SELECT * FROM matchmaking_queue WHERE status = 'SEARCHING' AND expires_at <= ?",
        (nowTs,),
    )
    for row in expiredRows:
        db.execute(
            "UPDATE matchmaking_queue SET status = 'EXPIRED' WHERE player_id = ? AND status = 'SEARCHING'",
            (row["player_id"],),
        )


def _getRecentOpponentId(db, playerId):
    pid = str(playerId)
    row = db.fetchOne(
        """
        SELECT player_1_id, player_2_id FROM matches
        WHERE player_1_id = ? OR player_2_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (pid, pid),
    )
    if not row:
        return None
    return str(row["player_2_id"]) if str(row["player_1_id"]) == pid else str(row["player_1_id"])


def joinMatchmaking(db, userId):
    uid = str(userId)
    _cleanupExpiredQueueEntries(db)

    profileRow = db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (uid,))
    if not profileRow:
        raise NotFoundError("Player profile not found")

    trophies = int(profileRow["trophies"])
    league = str(profileRow["league"])
    nowTs = time.time()
    expiresTs = nowTs + float(settings.matchmakingExpirationSeconds)

    existingEntry = db.fetchOne("SELECT * FROM matchmaking_queue WHERE player_id = ?", (uid,))
    if existingEntry:
        if existingEntry["status"] == "SEARCHING" and float(existingEntry["expires_at"]) > nowTs:
            return getMatchmakingStatus(db, uid, tryMatch=True)
        if existingEntry.get("match_id"):
            mModel = checkAndExpireMatch(db, existingEntry["match_id"])
            if mModel and mModel.status in ("MATCH_CREATED", "MAP_ASSIGNED", "AWAITING_RESULTS", "VERIFYING"):
                myRes = db.fetchOne(
                    "SELECT id FROM match_results WHERE match_id = ? AND player_id = ?",
                    (mModel.id, uid),
                )
                if not myRes:
                    return {
                        "success": True,
                        "state": mModel.status,
                        "match_id": mModel.id,
                        "match": formatMatchDetails(db, mModel.id, requestingPlayerId=uid),
                    }

    with db.transaction():
        db.execute("DELETE FROM matchmaking_queue WHERE player_id = ?", (uid,))
        db.execute(
            """
            INSERT INTO matchmaking_queue (player_id, trophies, league, status, match_id, joined_at, expires_at)
            VALUES (?, ?, ?, 'SEARCHING', NULL, ?, ?)
            """,
            (uid, trophies, league, nowTs, expiresTs),
        )

    wsManager.emitEvent(
        "matchmaking.started",
        {
            "player_id": uid,
            "state": "SEARCHING",
            "trophies": trophies,
            "league": league,
            "expires_at": expiresTs,
        },
        userId=uid,
        db=db,
    )

    return _attemptMatchmakingPair(db, uid)


def _attemptMatchmakingPair(db, userId):
    uid = str(userId)
    myEntry = db.fetchOne(
        "SELECT * FROM matchmaking_queue WHERE player_id = ? AND status = 'SEARCHING'",
        (uid,),
    )
    if not myEntry:
        return getMatchmakingStatus(db, uid, tryMatch=False)

    nowTs = time.time()
    myTrophies = int(myEntry["trophies"])
    myLeague = str(myEntry["league"])
    myWait = max(0.0, nowTs - float(myEntry["joined_at"]))

    candidates = db.fetchAll(
        "SELECT * FROM matchmaking_queue WHERE status = 'SEARCHING' AND player_id != ? AND expires_at > ?",
        (uid, nowTs),
    )
    if not candidates:
        return {
            "success": True,
            "state": "SEARCHING",
            "match_id": None,
            "trophies": myTrophies,
            "league": myLeague,
        }

    recentOpponentId = _getRecentOpponentId(db, uid)
    eligible = []
    for cand in candidates:
        cTrophies = int(cand["trophies"])
        cLeague = str(cand["league"])
        cWait = max(0.0, nowTs - float(cand["joined_at"]))
        maxWait = max(myWait, cWait)
        allowedDiff = int(settings.matchmakingInitialTrophyRange + maxWait * settings.matchmakingRangeExpansionPerSec)
        trophyDiff = abs(myTrophies - cTrophies)
        if trophyDiff <= allowedDiff:
            sameLeaguePenalty = 0 if cLeague == myLeague else 1
            repeatPenalty = 1 if (recentOpponentId and str(cand["player_id"]) == recentOpponentId and len(candidates) > 1) else 0
            eligible.append((repeatPenalty, sameLeaguePenalty, trophyDiff, float(cand["joined_at"]), cand))

    if not eligible:
        return {
            "success": True,
            "state": "SEARCHING",
            "match_id": None,
            "trophies": myTrophies,
            "league": myLeague,
        }

    eligible.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    chosen = eligible[0][4]
    opponentId = str(chosen["player_id"])

    matchModel, _ = createMatchForPlayers(db, opponentId, uid)
    return {
        "success": True,
        "state": "MAP_ASSIGNED",
        "match_id": matchModel.id,
        "match": formatMatchDetails(db, matchModel.id, requestingPlayerId=uid),
    }


def cancelMatchmaking(db, userId):
    uid = str(userId)
    row = db.fetchOne("SELECT * FROM matchmaking_queue WHERE player_id = ?", (uid,))
    if not row or row["status"] != "SEARCHING":
        return {"success": True, "state": "CANCELLED", "cancelled": False}

    with db.transaction():
        db.execute(
            "UPDATE matchmaking_queue SET status = 'CANCELLED' WHERE player_id = ? AND status = 'SEARCHING'",
            (uid,),
        )
    return {"success": True, "state": "CANCELLED", "cancelled": True}


def getMatchmakingStatus(db, userId, tryMatch=True):
    uid = str(userId)
    _cleanupExpiredQueueEntries(db)
    row = db.fetchOne("SELECT * FROM matchmaking_queue WHERE player_id = ?", (uid,))
    if not row:
        return {"success": True, "state": "IDLE", "match_id": None}

    if row["status"] == "SEARCHING" and tryMatch:
        return _attemptMatchmakingPair(db, uid)

    matchId = row.get("match_id")
    if matchId:
        mModel = checkAndExpireMatch(db, matchId)
        if mModel:
            return {
                "success": True,
                "state": mModel.status,
                "match_id": mModel.id,
                "match": formatMatchDetails(db, mModel.id, requestingPlayerId=uid),
            }

    return {
        "success": True,
        "state": str(row["status"]),
        "match_id": matchId,
    }
