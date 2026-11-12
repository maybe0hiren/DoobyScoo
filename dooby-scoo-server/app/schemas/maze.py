def formatMapAssignment(matchModel, mapModel):
    return {
        "match_id": matchModel.id,
        "map_id": mapModel.id,
        "map_version": mapModel.version,
        "map_hash": mapModel.mazeHash,
        "difficulty": mapModel.difficulty,
        "rules": matchModel.rules,
        "expires_at": matchModel.expiresAt,
        "maze": mapModel.mazeJson,
    }

