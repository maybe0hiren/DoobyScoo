def formatLeaderboardEntry(row, position):
    totalMatches = int(row.get("total_matches", 0))
    wins = int(row.get("wins", 0))
    winRate = round(float(wins) / float(totalMatches), 4) if totalMatches > 0 else 0.0
    return {
        "position": int(position),
        "player_id": str(row["user_id"]),
        "username": str(row["username"]),
        "display_name": str(row["display_name"]),
        "avatar": str(row.get("avatar") or "dog_default"),
        "level": int(row.get("level", 1)),
        "xp": int(row.get("xp", 0)),
        "trophies": int(row.get("trophies", 0)),
        "league": str(row.get("league") or "Beginner"),
        "wins": wins,
        "losses": int(row.get("losses", 0)),
        "draws": int(row.get("draws", 0)),
        "win_rate": winRate,
        "total_matches": totalMatches,
        "best_score": int(row["best_score"]) if row.get("best_score") is not None else None,
        "average_score": round(float(row["average_score"]), 2) if row.get("average_score") is not None else None,
        "dog_model_version": int(row.get("dog_model_version", 1)),
    }

