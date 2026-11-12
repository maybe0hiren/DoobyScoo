import json
import time
import uuid
from ..core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from ..core.security import (
    createAccessToken,
    createRefreshToken,
    decodeJwtToken,
    hashPassword,
    hashToken,
    nowIso,
    verifyPassword,
)
from ..models.player_profile import PlayerProfileModel
from ..models.user import UserModel
from ..schemas.auth import (
    validateLoginRequest,
    validatePasswordResetRequest,
    validateRefreshRequest,
    validateRegisterRequest,
)


def isUsernameAvailable(db, username):
    clean = str(username or "").strip()
    if not clean:
        return False
    row = db.fetchOne("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (clean,))
    return row is None


def registerUser(db, payload):
    data = validateRegisterRequest(payload)
    now = nowIso()
    userId = f"usr_{uuid.uuid4().hex[:16]}"
    pwHash = hashPassword(data["password"])

    with db.transaction():
        existingUser = db.fetchOne(
            "SELECT id, username, email FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (data["username"], data["email"]),
        )
        if existingUser:
            if existingUser["username"].lower() == data["username"].lower():
                raise ConflictError("Username is already taken", code="username_taken")
            raise ConflictError("Email is already registered", code="email_taken")

        db.execute(
            """
            INSERT INTO users (id, username, email, password_hash, display_name, avatar, settings_json, created_at, updated_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                userId,
                data["username"],
                data["email"],
                pwHash,
                data["displayName"],
                data["avatar"],
                json.dumps({"allow_post_match_learning": True}),
                now,
                now,
                now,
            ),
        )
        db.execute(
            """
            INSERT INTO player_profiles (
                user_id, level, xp, trophies, league, wins, losses, draws,
                best_score, average_score, total_matches, total_bones_collected,
                dog_model_version, dog_model_info
            )
            VALUES (?, 1, 0, 0, 'Beginner', 0, 0, 0, NULL, NULL, 0, 0, 1, ?)
            """,
            (userId, json.dumps({"architecture": "RecurrentPPO-LSTM", "observation_size": 8})),
        )
        accessToken = createAccessToken(userId, data["username"])
        refreshToken, tokenId, expTs = createRefreshToken(userId, data["username"])
        db.execute(
            """
            INSERT INTO refresh_tokens (token_id, user_id, token_hash, revoked, expires_at, created_at)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (tokenId, userId, hashToken(refreshToken), expTs, now),
        )

    user = UserModel.fromRow(db.fetchOne("SELECT * FROM users WHERE id = ?", (userId,)))
    profile = PlayerProfileModel.fromRow(db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (userId,)))
    return {
        "user": user,
        "profile": profile,
        "accessToken": accessToken,
        "refreshToken": refreshToken,
    }


def loginUser(db, payload):
    data = validateLoginRequest(payload)
    identifier = data["identifier"]
    row = db.fetchOne(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
        (identifier, identifier.lower()),
    )
    if not row or not verifyPassword(data["password"], row["password_hash"]):
        raise UnauthorizedError("Invalid username/email or password", code="invalid_credentials")

    now = nowIso()
    userId = str(row["id"])
    username = str(row["username"])
    accessToken = createAccessToken(userId, username)
    refreshToken, tokenId, expTs = createRefreshToken(userId, username)

    with db.transaction():
        db.execute("UPDATE users SET last_login = ?, updated_at = ? WHERE id = ?", (now, now, userId))
        db.execute(
            """
            INSERT INTO refresh_tokens (token_id, user_id, token_hash, revoked, expires_at, created_at)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (tokenId, userId, hashToken(refreshToken), expTs, now),
        )

    user = UserModel.fromRow(db.fetchOne("SELECT * FROM users WHERE id = ?", (userId,)))
    profile = PlayerProfileModel.fromRow(db.fetchOne("SELECT * FROM player_profiles WHERE user_id = ?", (userId,)))
    return {
        "user": user,
        "profile": profile,
        "accessToken": accessToken,
        "refreshToken": refreshToken,
    }


def logoutUser(db, userId, refreshToken=None):
    with db.transaction():
        if refreshToken:
            db.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ? AND token_hash = ?",
                (str(userId), hashToken(refreshToken)),
            )
        else:
            db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (str(userId),))
    return {"success": True, "message": "Logged out"}


def refreshAccessToken(db, payload):
    data = validateRefreshRequest(payload)
    rawToken = data["refreshToken"]
    claims = decodeJwtToken(rawToken, expectedType="refresh")
    userId = str(claims.get("sub") or "")
    tokenHash = hashToken(rawToken)

    row = db.fetchOne(
        "SELECT * FROM refresh_tokens WHERE token_hash = ? AND user_id = ?",
        (tokenHash, userId),
    )
    if not row or int(row.get("revoked", 0)) != 0 or float(row.get("expires_at", 0)) <= time.time():
        raise UnauthorizedError("Refresh token is invalid or revoked", code="refresh_token_invalid")

    userRow = db.fetchOne("SELECT * FROM users WHERE id = ?", (userId,))
    if not userRow:
        raise UnauthorizedError("User not found")

    now = nowIso()
    username = str(userRow["username"])
    newAccess = createAccessToken(userId, username)
    newRefresh, newTokenId, expTs = createRefreshToken(userId, username)

    with db.transaction():
        db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token_id = ?", (row["token_id"],))
        db.execute(
            """
            INSERT INTO refresh_tokens (token_id, user_id, token_hash, revoked, expires_at, created_at)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (newTokenId, userId, hashToken(newRefresh), expTs, now),
        )

    return {
        "accessToken": newAccess,
        "refreshToken": newRefresh,
        "user": UserModel.fromRow(userRow),
    }


def resetPassword(db, payload):
    data = validatePasswordResetRequest(payload)
    row = db.fetchOne(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?) AND LOWER(email) = LOWER(?)",
        (data["username"], data["email"]),
    )
    if not row:
        raise NotFoundError("No matching account found for username and email")

    now = nowIso()
    newHash = hashPassword(data["newPassword"])
    userId = str(row["id"])
    with db.transaction():
        db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (newHash, now, userId),
        )
        db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (userId,))
    return {"success": True, "message": "Password reset successfully"}

