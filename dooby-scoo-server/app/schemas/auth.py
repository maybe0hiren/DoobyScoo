import re
from ..core.exceptions import UnprocessableError

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,24}$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validateRegisterRequest(payload):
    if not isinstance(payload, dict):
        raise UnprocessableError("Request body must be a JSON object")
    username = str(payload.get("username") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    displayName = str(payload.get("display_name") or payload.get("displayName") or username).strip()
    avatar = str(payload.get("avatar") or "dog_default").strip()

    if not USERNAME_REGEX.match(username):
        raise UnprocessableError("Username must be 3-24 characters (letters, numbers, underscores)")
    if not EMAIL_REGEX.match(email):
        raise UnprocessableError("Invalid email address")
    if len(password) < 6:
        raise UnprocessableError("Password must be at least 6 characters long")
    if not displayName or len(displayName) > 36:
        raise UnprocessableError("Display name must be between 1 and 36 characters")

    return {
        "username": username,
        "email": email,
        "password": password,
        "displayName": displayName,
        "avatar": avatar,
    }


def validateLoginRequest(payload):
    if not isinstance(payload, dict):
        raise UnprocessableError("Request body must be a JSON object")
    identifier = str(payload.get("username") or payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    if not identifier or not password:
        raise UnprocessableError("Username/email and password are required")
    return {"identifier": identifier, "password": password}


def validateRefreshRequest(payload):
    if not isinstance(payload, dict):
        raise UnprocessableError("Request body must be a JSON object")
    refreshToken = str(payload.get("refresh_token") or payload.get("refreshToken") or "").strip()
    if not refreshToken:
        raise UnprocessableError("refresh_token is required")
    return {"refreshToken": refreshToken}


def validatePasswordResetRequest(payload):
    if not isinstance(payload, dict):
        raise UnprocessableError("Request body must be a JSON object")
    email = str(payload.get("email") or "").strip().lower()
    username = str(payload.get("username") or "").strip()
    newPassword = str(payload.get("new_password") or payload.get("newPassword") or "")
    if not email or not username or len(newPassword) < 6:
        raise UnprocessableError("username, email, and new_password (min 6 chars) are required")
    return {"email": email, "username": username, "newPassword": newPassword}

