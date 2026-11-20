import argparse
import time
from . import __version__
from .api import auth, battles, history, leaderboards, matches, matchmaking, profiles, users
from .config import settings
from .core.framework import ServerApplication, startBackgroundServer
from .core.security import nowIso
from .core.websocket_manager import wsManager
from .database.session import dbEngine, initDatabase
from .services.ranking_service import getGlobalLeaderboard, getLeagueLeaderboard


def createApp(databaseUrl=None, fallbackSqlitePath=None, resetDb=False):
    initDatabase(databaseUrl=databaseUrl, fallbackSqlitePath=fallbackSqlitePath, reset=resetDb)
    serverApp = ServerApplication(title=settings.appName, version=__version__)

    @serverApp.get("/health")
    def healthCheck(request, db):
        return {
            "status": "ok",
            "service": "dooby-scoo-server",
            "version": __version__,
            "timestamp": nowIso(),
        }

    @serverApp.get("/api/v1/health")
    def apiHealthCheck(request, db):
        return {
            "status": "ok",
            "service": "dooby-scoo-server",
            "version": __version__,
            "timestamp": nowIso(),
        }

    @serverApp.get("/openapi.json")
    def openApiRoot(request, db):
        return serverApp.generateOpenApiSpec()

    @serverApp.get("/api/v1/openapi.json")
    def openApiV1(request, db):
        return serverApp.generateOpenApiSpec()

    @serverApp.get("/api/v1/leaderboard")
    def singularLeaderboardEndpoint(request, db):
        limit = int(request.getQuery("limit", 50) or 50)
        offset = int(request.getQuery("offset", 0) or 0)
        league = request.getQuery("league", None)
        if league:
            res = getLeagueLeaderboard(db, league, limit=limit, offset=offset)
        else:
            res = getGlobalLeaderboard(db, limit=limit, offset=offset)
        return {"success": True, **res}

    @serverApp.get("/api/v1/status")
    def apiStatus(request, db):
        usersCountRow = db.fetchOne("SELECT COUNT(*) AS cnt FROM users")
        matchesCountRow = db.fetchOne("SELECT COUNT(*) AS cnt FROM matches")
        queueCountRow = db.fetchOne(
            "SELECT COUNT(*) AS cnt FROM matchmaking_queue WHERE status = 'SEARCHING' AND expires_at > ?",
            (time.time(),),
        )
        return {
            "success": True,
            "status": "online",
            "service": settings.appName,
            "version": __version__,
            "database_backend": "postgresql" if dbEngine.isPostgres else "sqlite_relational",
            "total_players": int(usersCountRow["cnt"]) if usersCountRow else 0,
            "total_matches": int(matchesCountRow["cnt"]) if matchesCountRow else 0,
            "searching_players": int(queueCountRow["cnt"]) if queueCountRow else 0,
            "online_ws_users": len(wsManager.connections),
            "timestamp": nowIso(),
        }

    serverApp.include_router(auth.router)
    serverApp.include_router(users.router)
    serverApp.include_router(profiles.router)
    serverApp.include_router(matchmaking.router)
    serverApp.include_router(matches.router)
    serverApp.include_router(battles.router)
    serverApp.include_router(leaderboards.router)
    serverApp.include_router(history.router)
    return serverApp


app = createApp()


def main():
    parser = argparse.ArgumentParser(description="DoobyScoo Authoritative Multiplayer Server")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()

    serverApp = createApp(databaseUrl=args.db) if args.db else app
    handle = startBackgroundServer(serverApp, host=args.host, port=args.port)
    print(f"DoobyScoo Multiplayer Server listening at http://{args.host}:{handle.port} (WS: ws://{args.host}:{handle.port}/ws)", flush=True)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        handle.stop()


if __name__ == "__main__":
    main()

