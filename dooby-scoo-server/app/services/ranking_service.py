from ..config import settings
from ..core.exceptions import NotFoundError
from ..schemas.leaderboard import formatLeaderboardEntry

LEADERBOARD_ORDER_SQL = """
    p.trophies DESC,
    CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END DESC,
    p.wins DESC,
    u.created_at ASC,
    u.id ASC
"""


def getGlobalLeaderboard(db, limit=50, offset=0):
    lim = max(1, min(100, int(limit or 50)))
    off = max(0, int(offset or 0))
    totalRow = db.fetchOne("SELECT COUNT(*) AS cnt FROM player_profiles")
    totalPlayers = int(totalRow["cnt"]) if totalRow else 0

    rows = db.fetchAll(
        f"""
        SELECT p.*, u.username, u.display_name, u.avatar, u.created_at
        FROM player_profiles p
        JOIN users u ON u.id = p.user_id
        ORDER BY {LEADERBOARD_ORDER_SQL}
        LIMIT ? OFFSET ?
        """,
        (lim, off),
    )
    entries = [formatLeaderboardEntry(row, off + idx + 1) for idx, row in enumerate(rows)]
    return {
        "total": totalPlayers,
        "limit": lim,
        "offset": off,
        "entries": entries,
    }


def getLeagueLeaderboard(db, leagueName, limit=50, offset=0):
    lim = max(1, min(100, int(limit or 50)))
    off = max(0, int(offset or 0))
    canonicalLeague = None
    for name, _, _ in settings.leagueThresholds:
        if name.lower() == str(leagueName or "").strip().lower():
            canonicalLeague = name
            break
    if canonicalLeague is None:
        raise NotFoundError(f"Unknown league '{leagueName}'")

    totalRow = db.fetchOne(
        "SELECT COUNT(*) AS cnt FROM player_profiles WHERE league = ?",
        (canonicalLeague,),
    )
    totalInLeague = int(totalRow["cnt"]) if totalRow else 0

    rows = db.fetchAll(
        f"""
        SELECT p.*, u.username, u.display_name, u.avatar, u.created_at
        FROM player_profiles p
        JOIN users u ON u.id = p.user_id
        WHERE p.league = ?
        ORDER BY {LEADERBOARD_ORDER_SQL}
        LIMIT ? OFFSET ?
        """,
        (canonicalLeague, lim, off),
    )
    entries = [formatLeaderboardEntry(row, off + idx + 1) for idx, row in enumerate(rows)]
    return {
        "league": canonicalLeague,
        "total": totalInLeague,
        "limit": lim,
        "offset": off,
        "entries": entries,
    }


def getPlayerPositionsAndNearby(db, userId, nearbyRadius=2):
    uid = str(userId)
    targetRow = db.fetchOne(
        """
        SELECT p.*, u.username, u.display_name, u.avatar, u.created_at
        FROM player_profiles p
        JOIN users u ON u.id = p.user_id
        WHERE p.user_id = ?
        """,
        (uid,),
    )
    if not targetRow:
        raise NotFoundError("Player profile not found")

    tTrophies = int(targetRow["trophies"])
    tMatches = int(targetRow["total_matches"])
    tWins = int(targetRow["wins"])
    tWinRate = float(tWins) / float(tMatches) if tMatches > 0 else 0.0
    tCreated = str(targetRow["created_at"])
    tLeague = str(targetRow["league"])

    aheadGlobalRow = db.fetchOne(
        """
        SELECT COUNT(*) AS cnt
        FROM player_profiles p
        JOIN users u ON u.id = p.user_id
        WHERE (p.trophies > ?)
           OR (p.trophies = ? AND (CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) > ? + 1e-9)
           OR (p.trophies = ? AND ABS((CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) - ?) <= 1e-9 AND p.wins > ?)
           OR (p.trophies = ? AND ABS((CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) - ?) <= 1e-9 AND p.wins = ? AND u.created_at < ?)
           OR (p.trophies = ? AND ABS((CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) - ?) <= 1e-9 AND p.wins = ? AND u.created_at = ? AND u.id < ?)
        """,
        (
            tTrophies,
            tTrophies, tWinRate,
            tTrophies, tWinRate, tWins,
            tTrophies, tWinRate, tWins, tCreated,
            tTrophies, tWinRate, tWins, tCreated, uid,
        ),
    )
    globalPosition = int(aheadGlobalRow["cnt"]) + 1 if aheadGlobalRow else 1

    aheadLeagueRow = db.fetchOne(
        """
        SELECT COUNT(*) AS cnt
        FROM player_profiles p
        JOIN users u ON u.id = p.user_id
        WHERE p.league = ? AND (
              (p.trophies > ?)
           OR (p.trophies = ? AND (CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) > ? + 1e-9)
           OR (p.trophies = ? AND ABS((CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) - ?) <= 1e-9 AND p.wins > ?)
           OR (p.trophies = ? AND ABS((CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) - ?) <= 1e-9 AND p.wins = ? AND u.created_at < ?)
           OR (p.trophies = ? AND ABS((CASE WHEN p.total_matches > 0 THEN CAST(p.wins AS REAL) / CAST(p.total_matches AS REAL) ELSE 0.0 END) - ?) <= 1e-9 AND p.wins = ? AND u.created_at = ? AND u.id < ?)
        )
        """,
        (
            tLeague,
            tTrophies,
            tTrophies, tWinRate,
            tTrophies, tWinRate, tWins,
            tTrophies, tWinRate, tWins, tCreated,
            tTrophies, tWinRate, tWins, tCreated, uid,
        ),
    )
    leaguePosition = int(aheadLeagueRow["cnt"]) + 1 if aheadLeagueRow else 1

    startOffset = max(0, globalPosition - 1 - int(nearbyRadius))
    windowSize = int(nearbyRadius) * 2 + 1
    nearbyRows = db.fetchAll(
        f"""
        SELECT p.*, u.username, u.display_name, u.avatar, u.created_at
        FROM player_profiles p
        JOIN users u ON u.id = p.user_id
        ORDER BY {LEADERBOARD_ORDER_SQL}
        LIMIT ? OFFSET ?
        """,
        (windowSize, startOffset),
    )
    nearbyPlayers = [
        formatLeaderboardEntry(row, startOffset + idx + 1)
        for idx, row in enumerate(nearbyRows)
    ]

    return {
        "player_id": uid,
        "username": str(targetRow["username"]),
        "trophies": tTrophies,
        "league": tLeague,
        "global_position": globalPosition,
        "league_position": leaguePosition,
        "nearby_players": nearbyPlayers,
    }


def getPlayerTrophyHistory(db, userId, limit=50, offset=0):
    lim = max(1, min(100, int(limit or 50)))
    off = max(0, int(offset or 0))
    rows = db.fetchAll(
        """
        SELECT * FROM trophy_history
        WHERE player_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (str(userId), lim, off),
    )
    return [
        {
            "id": str(r["id"]),
            "player_id": str(r["player_id"]),
            "match_id": str(r["match_id"]),
            "previous_trophies": int(r["previous_trophies"]),
            "trophy_change": int(r["trophy_change"]),
            "new_trophies": int(r["new_trophies"]),
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]

