SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        avatar TEXT NOT NULL DEFAULT 'dog_default',
        settings_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_login TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS player_profiles (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        level INTEGER NOT NULL DEFAULT 1,
        xp INTEGER NOT NULL DEFAULT 0,
        trophies INTEGER NOT NULL DEFAULT 0,
        league TEXT NOT NULL DEFAULT 'Beginner',
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        draws INTEGER NOT NULL DEFAULT 0,
        best_score INTEGER,
        average_score REAL,
        total_matches INTEGER NOT NULL DEFAULT 0,
        total_bones_collected INTEGER NOT NULL DEFAULT 0,
        dog_model_version INTEGER NOT NULL DEFAULT 1,
        dog_model_info TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS maps (
        id TEXT PRIMARY KEY,
        version INTEGER NOT NULL DEFAULT 1,
        difficulty TEXT NOT NULL,
        maze_json TEXT NOT NULL,
        maze_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS matches (
        id TEXT PRIMARY KEY,
        player_1_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        player_2_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        map_id TEXT NOT NULL REFERENCES maps(id),
        map_version INTEGER NOT NULL DEFAULT 1,
        map_hash TEXT NOT NULL,
        rules_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL,
        verification_status TEXT NOT NULL DEFAULT 'PENDING',
        winner_id TEXT REFERENCES users(id),
        created_at TEXT NOT NULL,
        started_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS match_results (
        id TEXT PRIMARY KEY,
        submission_id TEXT NOT NULL UNIQUE,
        match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        player_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        action_trace TEXT NOT NULL,
        claimed_score INTEGER NOT NULL,
        verified_score INTEGER NOT NULL,
        steps INTEGER NOT NULL,
        bones_collected INTEGER NOT NULL,
        completed INTEGER NOT NULL,
        final_position TEXT NOT NULL DEFAULT '[0, 0]',
        model_version INTEGER NOT NULL DEFAULT 1,
        verification_status TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        UNIQUE(match_id, player_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trophy_history (
        id TEXT PRIMARY KEY,
        player_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
        previous_trophies INTEGER NOT NULL,
        trophy_change INTEGER NOT NULL,
        new_trophies INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(player_id, match_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS matchmaking_queue (
        player_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        trophies INTEGER NOT NULL,
        league TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'SEARCHING',
        match_id TEXT,
        joined_at REAL NOT NULL,
        expires_at REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        token_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        revoked INTEGER NOT NULL DEFAULT 0,
        expires_at REAL NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ws_events (
        event_id TEXT PRIMARY KEY,
        seq_id INTEGER NOT NULL,
        user_id TEXT,
        match_id TEXT,
        event_type TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_profiles_trophies ON player_profiles(trophies DESC, wins DESC)",
    "CREATE INDEX IF NOT EXISTS idx_profiles_league ON player_profiles(league, trophies DESC)",
    "CREATE INDEX IF NOT EXISTS idx_matches_p1 ON matches(player_1_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_matches_p2 ON matches(player_2_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status, expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_trophy_history_player ON trophy_history(player_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_ws_events_user_seq ON ws_events(user_id, seq_id)",
]

DROP_STATEMENTS = [
    "DROP TABLE IF EXISTS ws_events",
    "DROP TABLE IF EXISTS refresh_tokens",
    "DROP TABLE IF EXISTS matchmaking_queue",
    "DROP TABLE IF EXISTS trophy_history",
    "DROP TABLE IF EXISTS match_results",
    "DROP TABLE IF EXISTS matches",
    "DROP TABLE IF EXISTS maps",
    "DROP TABLE IF EXISTS player_profiles",
    "DROP TABLE IF EXISTS users",
]

