import os
from pathlib import Path

DEFAULT_LEAGUE_THRESHOLDS = (
    ("Beginner", 0, 499),
    ("Bronze", 500, 999),
    ("Silver", 1000, 1499),
    ("Gold", 1500, 1999),
    ("Platinum", 2000, 2499),
    ("Diamond", 2500, 2999),
    ("Master", 3000, 999999999),
)


class Settings:
    def __init__(self):
        self.reload()

    def reload(self):
        self.appName = os.getenv("APP_NAME", "DoobyScoo Multiplayer Server")
        self.appEnv = os.getenv("APP_ENV", "development")
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.databaseUrl = os.getenv(
            "DATABASE_URL",
            "postgresql://doobyscoo:doobyscoo_dev_password@localhost:5432/doobyscoo",
        )
        defaultSqlite = str(Path(__file__).resolve().parent.parent / "doobyscoo_server.db")
        self.fallbackSqlitePath = os.getenv("FALLBACK_SQLITE_PATH", defaultSqlite)
        self.jwtSecretKey = os.getenv(
            "JWT_SECRET_KEY",
            "doobyscoo-dev-jwt-secret-key-replace-in-production-0123456789abcdef",
        )
        self.jwtAlgorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.accessTokenExpireMinutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.refreshTokenExpireDays = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
        self.corsOrigins = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
        self.matchExpirationSeconds = int(os.getenv("MATCH_EXPIRATION_SECONDS", "600"))
        self.matchmakingExpirationSeconds = int(os.getenv("MATCHMAKING_EXPIRATION_SECONDS", "180"))
        self.matchmakingInitialTrophyRange = int(os.getenv("MATCHMAKING_INITIAL_TROPHY_RANGE", "200"))
        self.matchmakingRangeExpansionPerSec = int(os.getenv("MATCHMAKING_RANGE_EXPANSION_PER_SEC", "25"))
        self.maxMatchSteps = int(os.getenv("MAX_MATCH_STEPS", "300"))
        self.trophyWinReward = int(os.getenv("TROPHY_WIN_REWARD", "25"))
        self.trophyLossPenalty = int(os.getenv("TROPHY_LOSS_PENALTY", "15"))
        self.trophyDrawReward = int(os.getenv("TROPHY_DRAW_REWARD", "5"))
        self.xpMatchParticipation = int(os.getenv("XP_MATCH_PARTICIPATION", "25"))
        self.xpMatchWin = int(os.getenv("XP_MATCH_WIN", "50"))
        self.xpPersonalBest = int(os.getenv("XP_PERSONAL_BEST", "30"))
        self.xpLeagueAdvancement = int(os.getenv("XP_LEAGUE_ADVANCEMENT", "100"))
        self.rateLimitPerMinute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "240"))
        self.maxRequestBytes = int(os.getenv("MAX_REQUEST_BYTES", str(1024 * 1024)))
        self.leagueThresholds = list(DEFAULT_LEAGUE_THRESHOLDS)

    def getLeagueForTrophies(self, trophies):
        tVal = max(0, int(trophies))
        for name, minT, maxT in self.leagueThresholds:
            if minT <= tVal <= maxT:
                return name
        return "Master"

    def getLeagueIndex(self, leagueName):
        for idx, (name, _, _) in enumerate(self.leagueThresholds):
            if name.lower() == str(leagueName).lower():
                return idx
        return 0


settings = Settings()

