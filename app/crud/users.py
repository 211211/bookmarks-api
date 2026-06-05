"""User data-access: lookup, registration, and authentication."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ConflictError
from app.core.security import hash_password, verify_password
from app.models import User

# A precomputed hash used to perform identical work when the email is unknown,
# so login timing doesn't reveal whether an account exists (user enumeration).
_DUMMY_HASH = hash_password("a-non-matching-dummy-password")


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_user(db: Session, *, username: str, email: str, password: str) -> User:
    """Register a new user. Raises ``ConflictError`` (409) on duplicate
    email/username; stores a bcrypt **hash**, never the raw password."""
    email = email.strip().lower()
    if get_by_email(db, email) is not None:
        raise ConflictError(
            "A user with this email already exists.",
            details={"field": "email", "constraint": "unique"},
        )
    if get_by_username(db, username) is not None:
        raise ConflictError(
            "This username is already taken.",
            details={"field": "username", "constraint": "unique"},
        )

    user = User(username=username, email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    """Verify credentials. Raises ``AuthError`` (401) on any mismatch, using a
    single generic message so we don't reveal whether the email exists."""
    user = get_by_email(db, email)
    if user is None:
        # Verify against a dummy hash so the response time matches the
        # wrong-password path and doesn't leak whether the email exists.
        verify_password(password, _DUMMY_HASH)
        raise AuthError("Invalid email or password.")
    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password.")
    return user
