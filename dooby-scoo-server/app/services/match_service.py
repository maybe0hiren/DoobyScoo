from datetime import datetime, timedelta, timezone
import json
import uuid
from ..config import settings
from ..core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from ..core.security import nowIso
from ..core.websocket_manager import wsManager
from ..models.match import MatchModel
from ..models.result import MatchResultModel
from ..schemas.match import validateSubmissionPayload
from ..schemas.maze import formatMapAssignment
from .map_generator import createAndStoreMap, difficultyForTrophies, getMapById
from .progression_service import applyPlayerMatchProgression
from .result_verifier import determineMatchWinner, verifyPlayerSubmission


def _parseIsoTimestamp(isoStr):
    if not isoStr:
        return None
    try:
        dt = datetime.fromisoformat(str(isoStr))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def createMatchForPlayers(db, player1Id, player2Id, difficulty=None, seed=None, expirationSeconds=None):
    p1 = str(player1Id)
    p2 = str(player2Id)
    if p1 == p2:
        raise BadRequestError("Cannot create a match of a player against themselves", code="self_match")

    p1Prof = db.fetchOne("SELECT trophies, league FROM player_profiles WHERE user_id = ?", (p1,))
    p2Prof = db.fetchOne("SELECT trophies, league FROM player_profiles WHERE user_id = ?", (p2,))
    avgTrophies = ((int(p1Prof["trophies"]) if p1Prof else 0) + (int(p2Prof["trophies"]) if p2Prof else 0)) // 2
    diff = difficulty or difficultyForTrophies(avgTrophies)

    expSecs = int(expirationSeconds if expirationSeconds is not None else settings.matchExpirationSeconds)
    nowDt = datetime.now(timezone.utc)
    createdIso = nowDt.isoformat()
    expiresIso = (nowDt + timedelta(seconds=expSecs)).isoformat()
    matchId = f"mtc_{uuid.uuid4().hex[:16]}"
    rules = {
        "max_steps": int(settings.maxMatchSteps),
        "bone_reward_value": 5,
        "scoring_formula": "steps - 5 * bones_collected",
        "lower_score_wins": True,
    }

    with db.transaction():
        mapModel = createAndStoreMap(db, difficulty=diff, seed=seed, version=1)
        db.execute(
            """
            INSERT INTO matches (
                id, player_1_id, player_2_id, map_id, map_version, map_hash,
                rules_json, status, verification_status, winner_id,
                created_at, started_at, expires_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'AWAITING_RESULTS', 'PENDING', NULL, ?, ?, ?, NULL)
            """,
            (
                matchId,
                p1,
                p2,
                mapModel.id,
                mapModel.version,
                mapModel.mazeHash,
                json.dumps(rules),
                createdIso,
                createdIso,
                expiresIso,
            ),
        )
        db.execute(
            "UPDATE matchmaking_queue SET status = 'MAP_ASSIGNED', match_id = ? WHERE player_id IN (?, ?)",
            (matchId, p1, p2),
        )

    p1User = db.fetchOne("SELECT id, username, display_name, avatar FROM users WHERE id = ?", (p1,))
    p2User = db.fetchOne("SELECT id, username, display_name, avatar FROM users WHERE id = ?", (p2,))

    wsManager.emitEvent(
        "matchmaking.opponent_found",
        {
            "match_id": matchId,
            "state": "OPPONENT_FOUND",
            "opponent": {
                "player_id": p2,
                "username": p2User["username"] if p2User else p2,
                "display_name": p2User["display_name"] if p2User else p2,
                "trophies": int(p2Prof["trophies"]) if p2Prof else 0,
                "league": p2Prof["league"] if p2Prof else "Beginner",
            },
        },
        userId=p1,
        matchId=matchId,
        db=db,
    )
    wsManager.emitEvent(
        "matchmaking.opponent_found",
        {
            "match_id": matchId,
            "state": "OPPONENT_FOUND",
            "opponent": {
                "player_id": p1,
                "username": p1User["username"] if p1User else p1,
                "display_name": p1User["display_name"] if p1User else p1,
                "trophies": int(p1Prof["trophies"]) if p1Prof else 0,
                "league": p1Prof["league"] if p1Prof else "Beginner",
            },
        },
        userId=p2,
        matchId=matchId,
        db=db,
    )

    wsManager.emitToUsers(
        [p1, p2],
        "match.created",
        {
            "match_id": matchId,
            "player_1_id": p1,
            "player_2_id": p2,
            "status": "MATCH_CREATED",
            "rules": rules,
            "expires_at": expiresIso,
        },
        matchId=matchId,
        db=db,
    )
    wsManager.emitToUsers(
        [p1, p2],
        "match.map_assigned",
        {
            "match_id": matchId,
            "map_id": mapModel.id,
            "map_version": mapModel.version,
            "map_hash": mapModel.mazeHash,
            "difficulty": mapModel.difficulty,
            "status": "MAP_ASSIGNED",
            "expires_at": expiresIso,
        },
        matchId=matchId,
        db=db,
    )

    matchRow = db.fetchOne("SELECT * FROM matches WHERE id = ?", (matchId,))
    return MatchModel.fromRow(matchRow), mapModel


def _getMatchResultsMap(db, matchId):
    rows = db.fetchAll("SELECT * FROM match_results WHERE match_id = ?", (str(matchId),))
    out = {}
    for r in rows:
        model = MatchResultModel.fromRow(r)
        out[model.playerId] = model
    return out


def _finalizeMatchTransaction(db, matchModel, res1, res2, expired=False):
    freshRow = db.fetchOne("SELECT * FROM matches WHERE id = ?", (matchModel.id,))
    if not freshRow or freshRow["status"] in ("COMPLETED", "EXPIRED", "CANCELLED"):
        return freshRow

    if res1 is None and res2 is None and expired:
        now = nowIso()
        db.execute(
            """
            UPDATE matches
            SET status = 'EXPIRED', verification_status = 'EXPIRED', completed_at = ?
            WHERE id = ?
            """,
            (now, matchModel.id),
        )
        db.execute(
            "UPDATE matchmaking_queue SET status = 'EXPIRED' WHERE match_id = ?",
            (matchModel.id,),
        )
        return db.fetchOne("SELECT * FROM matches WHERE id = ?", (matchModel.id,))

    decision = determineMatchWinner(
        matchModel.player1Id,
        res1,
        matchModel.player2Id,
        res2,
        allowDraw=True,
    )
    winnerId = decision["winnerId"]
    isDraw = decision["isDraw"]

    if isDraw or winnerId is None:
        outcome1, outcome2 = "draw", "draw"
    elif winnerId == matchModel.player1Id:
        outcome1, outcome2 = "win", "loss"
    else:
        outcome1, outcome2 = "loss", "win"

    prog1 = applyPlayerMatchProgression(db, matchModel.id, matchModel.player1Id, outcome1, res1)
    prog2 = applyPlayerMatchProgression(db, matchModel.id, matchModel.player2Id, outcome2, res2)

    now = nowIso()
    finalStatus = "COMPLETED"
    db.execute(
        """
        UPDATE matches
        SET status = ?, verification_status = 'VERIFIED', winner_id = ?, completed_at = ?
        WHERE id = ?
        """,
        (finalStatus, winnerId, now, matchModel.id),
    )
    db.execute(
        "UPDATE matchmaking_queue SET status = 'COMPLETED' WHERE match_id = ?",
        (matchModel.id,),
    )
    updatedRow = db.fetchOne("SELECT * FROM matches WHERE id = ?", (matchModel.id,))
    return {
        "matchRow": updatedRow,
        "decision": decision,
        "progression": {
            matchModel.player1Id: prog1,
            matchModel.player2Id: prog2,
        },
    }


def _emitMatchCompletionEvents(db, matchModel, finalizeData):
    if not isinstance(finalizeData, dict) or "progression" not in finalizeData:
        return
    decision = finalizeData["decision"]
    progMap = finalizeData["progression"]
    winnerId = decision["winnerId"]

    resultsByPlayer = _getMatchResultsMap(db, matchModel.id)
    r1 = resultsByPlayer.get(matchModel.player1Id)
    r2 = resultsByPlayer.get(matchModel.player2Id)

    summaryPayload = {
        "match_id": matchModel.id,
        "status": "COMPLETED",
        "winner_id": winnerId,
        "is_draw": decision["isDraw"],
        "reason": decision["reason"],
        "player_1": {
            "player_id": matchModel.player1Id,
            "verified_score": r1.verifiedScore if r1 else None,
            "steps": r1.steps if r1 else None,
            "bones_collected": r1.bonesCollected if r1 else None,
            "completed": r1.completed if r1 else False,
            "trophy_change": progMap[matchModel.player1Id]["trophyChange"],
            "new_trophies": progMap[matchModel.player1Id]["newTrophies"],
            "xp_awarded": progMap[matchModel.player1Id]["xpAwarded"],
            "league": progMap[matchModel.player1Id]["newLeague"],
        },
        "player_2": {
            "player_id": matchModel.player2Id,
            "verified_score": r2.verifiedScore if r2 else None,
            "steps": r2.steps if r2 else None,
            "bones_collected": r2.bonesCollected if r2 else None,
            "completed": r2.completed if r2 else False,
            "trophy_change": progMap[matchModel.player2Id]["trophyChange"],
            "new_trophies": progMap[matchModel.player2Id]["newTrophies"],
            "xp_awarded": progMap[matchModel.player2Id]["xpAwarded"],
            "league": progMap[matchModel.player2Id]["newLeague"],
        },
    }

    wsManager.emitToUsers(
        [matchModel.player1Id, matchModel.player2Id],
        "match.completed",
        summaryPayload,
        matchId=matchModel.id,
        db=db,
    )

    for pid in (matchModel.player1Id, matchModel.player2Id):
        pData = progMap[pid]
        wsManager.emitEvent(
            "player.trophies_updated",
            {
                "match_id": matchModel.id,
                "previous_trophies": pData["previousTrophies"],
                "trophy_change": pData["trophyChange"],
                "new_trophies": pData["newTrophies"],
                "league": pData["newLeague"],
            },
            userId=pid,
            matchId=matchModel.id,
            db=db,
        )
        wsManager.emitEvent(
            "player.profile_updated",
            {
                "player_id": pid,
                "level": pData["newLevel"],
                "xp": pData["newXp"],
                "xp_awarded": pData["xpAwarded"],
                "trophies": pData["newTrophies"],
                "league": pData["newLeague"],
                "wins": pData["wins"],
                "losses": pData["losses"],
                "draws": pData["draws"],
                "best_score": pData["bestScore"],
                "average_score": pData["averageScore"],
            },
            userId=pid,
            matchId=matchModel.id,
            db=db,
        )

    wsManager.emitEvent(
        "leaderboard.updated",
        {"match_id": matchModel.id, "updated_players": [matchModel.player1Id, matchModel.player2Id]},
        userId=None,
        matchId=matchModel.id,
        db=db,
    )


def checkAndExpireMatch(db, matchId):
    row = db.fetchOne("SELECT * FROM matches WHERE id = ?", (str(matchId),))
    if not row:
        return None
    matchModel = MatchModel.fromRow(row)
    if matchModel.status in ("COMPLETED", "EXPIRED", "CANCELLED"):
        return matchModel

    expTs = _parseIsoTimestamp(matchModel.expiresAt)
    nowTs = datetime.now(timezone.utc).timestamp()
    if expTs is not None and nowTs > expTs:
        resultsMap = _getMatchResultsMap(db, matchModel.id)
        res1 = resultsMap.get(matchModel.player1Id)
        res2 = resultsMap.get(matchModel.player2Id)

        with db.transaction():
            fin = _finalizeMatchTransaction(db, matchModel, res1, res2, expired=True)

        wsManager.emitToUsers(
            [matchModel.player1Id, matchModel.player2Id],
            "match.expired",
            {
                "match_id": matchModel.id,
                "status": "EXPIRED" if (res1 is None and res2 is None) else "COMPLETED",
                "expires_at": matchModel.expiresAt,
            },
            matchId=matchModel.id,
            db=db,
        )
        if isinstance(fin, dict) and "progression" in fin:
            _emitMatchCompletionEvents(db, matchModel, fin)
        return MatchModel.fromRow(db.fetchOne("SELECT * FROM matches WHERE id = ?", (matchModel.id,)))

    return matchModel


def getMatchForPlayer(db, matchId, playerId):
    matchModel = checkAndExpireMatch(db, matchId)
    if not matchModel:
        raise NotFoundError("Match not found")
    if str(playerId) not in (matchModel.player1Id, matchModel.player2Id):
        raise ForbiddenError("You are not a participant in this match")
    return matchModel


def getMatchMapPayload(db, matchId, playerId):
    matchModel = getMatchForPlayer(db, matchId, playerId)
    mapModel = getMapById(db, matchModel.mapId)
    if not mapModel:
        raise NotFoundError("Assigned map not found")
    return formatMapAssignment(matchModel, mapModel)


def submitMatchResult(db, matchId, playerId, payload):
    row = db.fetchOne("SELECT * FROM matches WHERE id = ?", (str(matchId),))
    if not row:
        raise NotFoundError("Match not found")
    matchModel = MatchModel.fromRow(row)
    pid = str(playerId)
    if pid not in (matchModel.player1Id, matchModel.player2Id):
        raise ForbiddenError("You are not a participant in this match")

    existingForPlayer = db.fetchOne(
        "SELECT * FROM match_results WHERE match_id = ? AND player_id = ?",
        (matchModel.id, pid),
    )
    reqSubId = str(payload.get("submission_id") or payload.get("submissionId") or "").strip() if isinstance(payload, dict) else ""
    if existingForPlayer:
        if reqSubId and str(existingForPlayer["submission_id"]) == reqSubId:
            existingModel = MatchResultModel.fromRow(existingForPlayer)
            return formatMatchDetails(db, matchModel.id, pid, includeIdempotentFlag=True, submissionModel=existingModel)
        raise ConflictError("Result already submitted for this match", code="duplicate_submission")

    matchModel = checkAndExpireMatch(db, matchId)
    if matchModel.status == "EXPIRED":
        raise BadRequestError("Match has expired; submissions are closed", code="match_expired")
    if matchModel.status == "CANCELLED":
        raise BadRequestError("Match was cancelled", code="match_cancelled")
    if matchModel.status == "COMPLETED":
        raise ConflictError("Match is already completed", code="match_already_completed")

    subData = validateSubmissionPayload(payload, matchModel.id, pid)
    mapModel = getMapById(db, matchModel.mapId)
    if not mapModel:
        raise NotFoundError("Match map not found")

    verified = verifyPlayerSubmission(matchModel, mapModel, subData)
    resultId = f"res_{uuid.uuid4().hex[:16]}"
    submittedAt = nowIso()

    finalizeData = None
    bothSubmitted = False

    with db.transaction():
        dupCheck = db.fetchOne(
            "SELECT * FROM match_results WHERE match_id = ? AND player_id = ?",
            (matchModel.id, pid),
        )
        if dupCheck:
            if str(dupCheck["submission_id"]) == subData["submissionId"]:
                existingModel = MatchResultModel.fromRow(dupCheck)
                return formatMatchDetails(db, matchModel.id, pid, includeIdempotentFlag=True, submissionModel=existingModel)
            raise ConflictError("Result already submitted for this match", code="duplicate_submission")

        db.execute(
            """
            INSERT INTO match_results (
                id, submission_id, match_id, player_id, action_trace,
                claimed_score, verified_score, steps, bones_collected,
                completed, final_position, model_version, verification_status, submitted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED', ?)
            """,
            (
                resultId,
                subData["submissionId"],
                matchModel.id,
                pid,
                json.dumps(verified["normalizedActions"]),
                subData["claimedScore"],
                verified["verifiedScore"],
                verified["steps"],
                verified["bonesCollected"],
                1 if verified["completed"] else 0,
                json.dumps(verified["finalPosition"]),
                subData["modelVersion"],
                submittedAt,
            ),
        )

        resultsMap = _getMatchResultsMap(db, matchModel.id)
        res1 = resultsMap.get(matchModel.player1Id)
        res2 = resultsMap.get(matchModel.player2Id)
        if res1 is not None and res2 is not None:
            bothSubmitted = True
            db.execute(
                "UPDATE matches SET status = 'VERIFYING', verification_status = 'VERIFYING' WHERE id = ?",
                (matchModel.id,),
            )
            finalizeData = _finalizeMatchTransaction(db, matchModel, res1, res2, expired=False)

    opponentId = matchModel.player2Id if pid == matchModel.player1Id else matchModel.player1Id
    wsManager.emitEvent(
        "match.opponent_submitted",
        {
            "match_id": matchModel.id,
            "submitted_by": pid,
            "status": "COMPLETED" if bothSubmitted else "AWAITING_RESULTS",
        },
        userId=opponentId,
        matchId=matchModel.id,
        db=db,
    )

    if bothSubmitted:
        wsManager.emitToUsers(
            [matchModel.player1Id, matchModel.player2Id],
            "match.verification_started",
            {"match_id": matchModel.id, "status": "VERIFYING"},
            matchId=matchModel.id,
            db=db,
        )
        _emitMatchCompletionEvents(db, matchModel, finalizeData)

    savedResult = MatchResultModel.fromRow(
        db.fetchOne("SELECT * FROM match_results WHERE id = ?", (resultId,))
    )
    return formatMatchDetails(db, matchModel.id, pid, submissionModel=savedResult)


def formatMatchDetails(db, matchId, requestingPlayerId=None, includeIdempotentFlag=False, submissionModel=None):
    matchModel = checkAndExpireMatch(db, matchId)
    if not matchModel:
        raise NotFoundError("Match not found")
    if requestingPlayerId is not None and str(requestingPlayerId) not in (matchModel.player1Id, matchModel.player2Id):
        raise ForbiddenError("You are not a participant in this match")

    p1Row = db.fetchOne("SELECT id, username, display_name, avatar FROM users WHERE id = ?", (matchModel.player1Id,))
    p2Row = db.fetchOne("SELECT id, username, display_name, avatar FROM users WHERE id = ?", (matchModel.player2Id,))
    resultsMap = _getMatchResultsMap(db, matchModel.id)
    r1 = resultsMap.get(matchModel.player1Id)
    r2 = resultsMap.get(matchModel.player2Id)

    trophyRows = db.fetchAll("SELECT * FROM trophy_history WHERE match_id = ?", (matchModel.id,))
    trophyByPlayer = {str(r["player_id"]): r for r in trophyRows}

    def _serializeResult(res, uid):
        if res is None:
            return None
        tr = trophyByPlayer.get(str(uid))
        return {
            "submission_id": res.submissionId,
            "player_id": res.playerId,
            "claimed_score": res.claimedScore,
            "verified_score": res.verifiedScore,
            "steps": res.steps,
            "bones_collected": res.bonesCollected,
            "completed": res.completed,
            "final_position": res.finalPosition,
            "model_version": res.modelVersion,
            "verification_status": res.verificationStatus,
            "submitted_at": res.submittedAt,
            "trophy_change": int(tr["trophy_change"]) if tr else None,
            "new_trophies": int(tr["new_trophies"]) if tr else None,
        }

    out = {
        "success": True,
        "match_id": matchModel.id,
        "status": matchModel.status,
        "verification_status": matchModel.verificationStatus,
        "map_id": matchModel.mapId,
        "map_version": matchModel.mapVersion,
        "map_hash": matchModel.mapHash,
        "rules": matchModel.rules,
        "winner_id": matchModel.winnerId,
        "is_draw": (matchModel.status == "COMPLETED" and matchModel.winnerId is None),
        "created_at": matchModel.createdAt,
        "started_at": matchModel.startedAt,
        "expires_at": matchModel.expiresAt,
        "completed_at": matchModel.completedAt,
        "player_1": {
            "player_id": matchModel.player1Id,
            "username": p1Row["username"] if p1Row else matchModel.player1Id,
            "display_name": p1Row["display_name"] if p1Row else matchModel.player1Id,
            "avatar": p1Row["avatar"] if p1Row else "dog_default",
            "submitted": r1 is not None,
            "submission": _serializeResult(r1, matchModel.player1Id),
        },
        "player_2": {
            "player_id": matchModel.player2Id,
            "username": p2Row["username"] if p2Row else matchModel.player2Id,
            "display_name": p2Row["display_name"] if p2Row else matchModel.player2Id,
            "avatar": p2Row["avatar"] if p2Row else "dog_default",
            "submitted": r2 is not None,
            "submission": _serializeResult(r2, matchModel.player2Id),
        },
    }
    if submissionModel is not None:
        out["my_submission"] = _serializeResult(submissionModel, submissionModel.playerId)
    if includeIdempotentFlag:
        out["idempotent"] = True
    return out


def getPlayerMatchHistory(db, playerId, limit=50, offset=0):
    pid = str(playerId)
    lim = max(1, min(100, int(limit or 50)))
    off = max(0, int(offset or 0))
    rows = db.fetchAll(
        """
        SELECT * FROM matches
        WHERE player_1_id = ? OR player_2_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (pid, pid, lim, off),
    )
    items = []
    for row in rows:
        items.append(formatMatchDetails(db, row["id"], requestingPlayerId=pid))
    return {
        "player_id": pid,
        "count": len(items),
        "limit": lim,
        "offset": off,
        "matches": items,
    }

