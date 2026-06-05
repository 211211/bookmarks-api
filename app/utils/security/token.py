"""JWT access-token provider."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.utils.security.interface import ITokenProvider

TOKEN_TYPE = "access"


class JwtTokenProvider(ITokenProvider):
    """Issues and verifies HS256-signed JWT access tokens."""

    def __init__(self, *, secret: str, algorithm: str, expires_minutes: int) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._expires_minutes = expires_minutes

    def create_access_token(self, subject: int | str, expires_minutes: int | None = None) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=expires_minutes or self._expires_minutes)
        payload = {
            "sub": str(subject),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": TOKEN_TYPE,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> dict:
        payload = jwt.decode(
            token,
            self._secret,
            algorithms=[self._algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
        if payload.get("type") != TOKEN_TYPE:
            raise jwt.InvalidTokenError("Unexpected token type.")
        return payload
