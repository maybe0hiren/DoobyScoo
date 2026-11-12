import time
import threading
from ..config import settings
from ..database.session import getDb
from ..models.user import UserModel
from .exceptions import RateLimitError, UnauthorizedError
from .security import decodeJwtToken


class RateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.buckets = {}

    def check(self, key):
        limit = int(settings.rateLimitPerMinute)
        if limit <= 0:
            return
        now = time.time()
        windowStart = now - 60.0
        with self.lock:
            history = self.buckets.get(key, [])
            history = [t for t in history if t > windowStart]
            if len(history) >= limit:
                self.buckets[key] = history
                raise RateLimitError("Rate limit exceeded. Try again shortly.")
            history.append(now)
            self.buckets[key] = history

    def reset(self):
        with self.lock:
            self.buckets.clear()


rateLimiter = RateLimiter()


def extractBearerToken(headers, queryParams=None):
    authHeader = ""
    if isinstance(headers, dict):
        for k, v in headers.items():
            if k.lower() == "authorization":
                authHeader = str(v)
                break
    elif hasattr(headers, "get"):
        authHeader = str(headers.get("Authorization") or headers.get("authorization") or "")

    if authHeader.lower().startswith("bearer "):
        return authHeader[7:].strip()
    if queryParams and isinstance(queryParams, dict) and queryParams.get("token"):
        val = queryParams["token"]
        return val[0] if isinstance(val, list) else str(val)
    raise UnauthorizedError("Missing or invalid Authorization Bearer token")


def getCurrentUserFromToken(token, db=None):
    session = db or getDb()
    claims = decodeJwtToken(token, expectedType="access")
    userId = claims.get("sub")
    if not userId:
        raise UnauthorizedError("Invalid token subject")
    row = session.fetchOne("SELECT * FROM users WHERE id = ?", (str(userId),))
    if not row:
        raise UnauthorizedError("Account no longer exists")
    return UserModel.fromRow(row)


def getCurrentUser(request, db=None):
    token = extractBearerToken(request.headers, getattr(request, "queryParams", None))
    return getCurrentUserFromToken(token, db=db)

