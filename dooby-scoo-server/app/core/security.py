import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import time
import uuid
from ..config import settings
from .exceptions import UnauthorizedError

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
    _ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
except ImportError:
    _ph = None


def nowIso():
    return datetime.now(timezone.utc).isoformat()


def hashPassword(password):
    raw = str(password)
    if _ph is not None:
        return _ph.hash(raw)
    salt = uuid.uuid4().hex
    digest = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verifyPassword(password, passwordHash):
    raw = str(password)
    stored = str(passwordHash or "")
    if stored.startswith("pbkdf2_sha256$"):
        parts = stored.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected = parts
        actual = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
        return hmac.compare_digest(actual, expected)
    if _ph is not None:
        try:
            return bool(_ph.verify(stored, raw))
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            return False
    return False


def _b64UrlEncode(dataBytes):
    return base64.urlsafe_b64encode(dataBytes).rstrip(b"=").decode("ascii")


def _b64UrlDecode(text):
    padded = str(text) + "=" * ((4 - len(str(text)) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def createJwtToken(payload, expiresInSeconds=None):
    nowTs = time.time()
    expTs = nowTs + (
        float(expiresInSeconds)
        if expiresInSeconds is not None
        else float(settings.accessTokenExpireMinutes * 60)
    )
    claims = dict(payload)
    claims.setdefault("iat", nowTs)
    claims["exp"] = expTs
    claims.setdefault("jti", uuid.uuid4().hex)

    header = {"alg": "HS256", "typ": "JWT"}
    headerB64 = _b64UrlEncode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payloadB64 = _b64UrlEncode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signingInput = f"{headerB64}.{payloadB64}".encode("ascii")
    signature = hmac.new(settings.jwtSecretKey.encode("utf-8"), signingInput, hashlib.sha256).digest()
    sigB64 = _b64UrlEncode(signature)
    return f"{headerB64}.{payloadB64}.{sigB64}"


def decodeJwtToken(token, expectedType=None):
    if not token or not isinstance(token, str):
        raise UnauthorizedError("Missing authentication token")
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise UnauthorizedError("Malformed authentication token")
    headerB64, payloadB64, sigB64 = parts
    signingInput = f"{headerB64}.{payloadB64}".encode("ascii")
    expectedSig = _b64UrlEncode(
        hmac.new(settings.jwtSecretKey.encode("utf-8"), signingInput, hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sigB64, expectedSig):
        raise UnauthorizedError("Invalid token signature")
    try:
        claims = json.loads(_b64UrlDecode(payloadB64).decode("utf-8"))
    except Exception as exc:
        raise UnauthorizedError("Invalid token payload") from exc

    exp = claims.get("exp")
    if exp is None or float(exp) <= time.time():
        raise UnauthorizedError("Token has expired", code="token_expired")
    if expectedType and claims.get("type") != expectedType:
        raise UnauthorizedError(f"Expected {expectedType} token")
    return claims


def createAccessToken(userId, username, expiresInSeconds=None):
    ttl = (
        float(expiresInSeconds)
        if expiresInSeconds is not None
        else float(settings.accessTokenExpireMinutes * 60)
    )
    return createJwtToken(
        {"sub": str(userId), "username": str(username), "type": "access"},
        expiresInSeconds=ttl,
    )


def createRefreshToken(userId, username, expiresInSeconds=None):
    ttl = (
        float(expiresInSeconds)
        if expiresInSeconds is not None
        else float(settings.refreshTokenExpireDays * 86400)
    )
    jti = uuid.uuid4().hex
    token = createJwtToken(
        {"sub": str(userId), "username": str(username), "type": "refresh", "jti": jti},
        expiresInSeconds=ttl,
    )
    return token, jti, time.time() + ttl


def hashToken(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

