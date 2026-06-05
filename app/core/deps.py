"""Reusable FastAPI dependencies — notably the auth dependency that resolves the
current user from a bearer JWT. Kept separate from route logic on purpose."""

from __future__ import annotations

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthError
from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

# `auto_error=False` lets us raise our own consistent 401 envelope instead of
# FastAPI's default. The scheme name surfaces in the OpenAPI spec / Swagger
# "Authorize" dialog.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve and return the authenticated user, or raise ``AuthError`` (401)."""
    if credentials is None or not credentials.credentials:
        raise AuthError("Authentication credentials were not provided.")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid authentication token.") from exc

    subject = payload.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise AuthError("Invalid authentication token.") from exc

    user = db.get(User, user_id)
    if user is None:
        raise AuthError("User account no longer exists.")
    return user
