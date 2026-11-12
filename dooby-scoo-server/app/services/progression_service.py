import uuid
from ..config import settings
from ..core.security import nowIso
from ..models.player_profile import PlayerProfileModel


def calculateXpLevel(totalXp):
    return max(1, 1 + (max(0, int(totalXp)) // 100))


def applyPlayerMatchProgression(db, matchId, playerId, outcome, resultModel):
    existingHistory = db.fetchOne(
        "SELECT * FROM trophy_history WHERE player_id = ? AND match_id = ?",
        (str(playerId), str(matchId)),
    )
    profileRow = db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (str(playerId),))
    if not profileRow:
        raise ValueError(f"Profile not found for player {playerId}")
    profile = PlayerProfileModel.fromRow(profileRow)

    if existingHistory:
        return {
            "playerId": str(playerId),
            "previousTrophies": int(existingHistory["previous_trophies"]),
            "trophyChange": int(existingHistory["trophy_change"]),
            "newTrophies": int(existingHistory["new_trophies"]),
            "xpAwarded": 0,
            "newXp": profile.xp,
            "newLevel": profile.level,
            "oldLeague": profile.league,
            "newLeague": profile.league,
            "alreadyApplied": True,
        }

    prevTrophies = int(profile.trophies)
    if outcome == "win":
        rawChange = int(settings.trophyWinReward)
        newTrophies = prevTrophies + rawChange
        winsDelta, lossesDelta, drawsDelta = 1, 0, 0
    elif outcome == "loss":
        rawChange = -int(settings.trophyLossPenalty)
        newTrophies = max(0, prevTrophies + rawChange)
        winsDelta, lossesDelta, drawsDelta = 0, 1, 0
    else:
        rawChange = int(settings.trophyDrawReward)
        newTrophies = prevTrophies + rawChange
        winsDelta, lossesDelta, drawsDelta = 0, 0, 1

    actualTrophyChange = newTrophies - prevTrophies
    oldLeague = profile.league
    newLeague = settings.getLeagueForTrophies(newTrophies)
    leagueAdvanced = settings.getLeagueIndex(newLeague) > settings.getLeagueIndex(oldLeague)

    xpAwarded = int(settings.xpMatchParticipation)
    if outcome == "win":
        xpAwarded += int(settings.xpMatchWin)

    newBestScore = profile.bestScore
    reachedPersonalBest = False
    if resultModel is not None and resultModel.completed:
        if newBestScore is None or int(resultModel.verifiedScore) < int(newBestScore):
            newBestScore = int(resultModel.verifiedScore)
            reachedPersonalBest = True
            xpAwarded += int(settings.xpPersonalBest)

    if leagueAdvanced:
        xpAwarded += int(settings.xpLeagueAdvancement)

    newXp = int(profile.xp) + xpAwarded
    newLevel = calculateXpLevel(newXp)
    newTotalMatches = int(profile.totalMatches) + 1
    newWins = int(profile.wins) + winsDelta
    newLosses = int(profile.losses) + lossesDelta
    newDraws = int(profile.draws) + drawsDelta

    bonesAdded = int(resultModel.bonesCollected) if resultModel is not None else 0
    newTotalBones = int(profile.totalBonesCollected) + bonesAdded

    if resultModel is not None:
        if profile.averageScore is None or profile.totalMatches <= 0:
            newAvgScore = float(resultModel.verifiedScore)
        else:
            prevTotalScore = float(profile.averageScore) * float(profile.totalMatches)
            newAvgScore = round((prevTotalScore + float(resultModel.verifiedScore)) / float(newTotalMatches), 2)
        newModelVersion = max(int(profile.dogModelVersion), int(resultModel.modelVersion))
    else:
        newAvgScore = profile.averageScore
        newModelVersion = profile.dogModelVersion

    db.execute(
        """
        UPDATE player_profiles
        SET level = ?,
            xp = ?,
            trophies = ?,
            league = ?,
            wins = ?,
            losses = ?,
            draws = ?,
            best_score = ?,
            average_score = ?,
            total_matches = ?,
            total_bones_collected = ?,
            dog_model_version = ?
        WHERE user_id = ?
        """,
        (
            newLevel,
            newXp,
            newTrophies,
            newLeague,
            newWins,
            newLosses,
            newDraws,
            newBestScore,
            newAvgScore,
            newTotalMatches,
            newTotalBones,
            newModelVersion,
            str(playerId),
        ),
    )

    historyId = f"trp_{uuid.uuid4().hex[:16]}"
    db.execute(
        """
        INSERT INTO trophy_history (id, player_id, match_id, previous_trophies, trophy_change, new_trophies, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            historyId,
            str(playerId),
            str(matchId),
            prevTrophies,
            actualTrophyChange,
            newTrophies,
            nowIso(),
        ),
    )

    return {
        "playerId": str(playerId),
        "outcome": outcome,
        "previousTrophies": prevTrophies,
        "trophyChange": actualTrophyChange,
        "newTrophies": newTrophies,
        "xpAwarded": xpAwarded,
        "newXp": newXp,
        "newLevel": newLevel,
        "oldLeague": oldLeague,
        "newLeague": newLeague,
        "leagueAdvanced": leagueAdvanced,
        "reachedPersonalBest": reachedPersonalBest,
        "bestScore": newBestScore,
        "averageScore": newAvgScore,
        "totalMatches": newTotalMatches,
        "wins": newWins,
        "losses": newLosses,
        "draws": newDraws,
    }

