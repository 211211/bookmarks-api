"""Password hashing (bcrypt) and JWT creation/verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
import jwt

# Compatibility shim: passlib 1.7.4 probes ``bcrypt.__about__.__version__``,
# which bcrypt >= 4.1 removed. Provide it so the bcrypt backend loads cleanly
# (without this, passlib logs a harmless but noisy traceback on first use).
if not hasattr(_bcrypt, "__about__"):  # pragma: no cover - environment shim

    class _About:
        __version__ = getattr(_bcrypt, "__version__", "4.1.0")

    _bcrypt.__about__ = _About  # type: ignore[attr-defined]

from passlib.context import CryptContext  # noqa: E402

from app.config import get_settings  # noqa: E402

settings = get_settings()

# bcrypt is a one-way password *hash* (with per-password salt) — never reversible
# encryption. `deprecated="auto"` lets us migrate schemes later transparently.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: int | str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT whose subject (`sub`) identifies the user."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes or settings.jwt_expires_minutes)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT. Raises ``jwt.ExpiredSignatureError`` /
    ``jwt.InvalidTokenError`` on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub"]},
    )
