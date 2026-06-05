"""Auth service implementation."""

from __future__ import annotations

import functools

from app.core.errors import AuthError, ConflictError
from app.models import User
from app.repositories.user.interface import IUserRepository
from app.services.auth.interface import IAuthService
from app.utils.security.interface import IPasswordHasher, ITokenProvider


@functools.lru_cache(maxsize=8)
def _dummy_hash(hasher: IPasswordHasher) -> str:
    """Cache a throwaway hash per hasher instance (the prod hasher is a singleton,
    so the bcrypt cost is paid once) for constant-time failed logins."""
    return hasher.hash("a-non-matching-dummy-password")


class AuthService(IAuthService):
    def __init__(
        self,
        users: IUserRepository,
        hasher: IPasswordHasher,
        tokens: ITokenProvider,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    def register(self, *, username: str, email: str, password: str) -> tuple[User, str]:
        email = email.strip().lower()
        if self._users.get_by_email(email) is not None:
            raise ConflictError(
                "A user with this email already exists.",
                details={"field": "email", "constraint": "unique"},
            )
        if self._users.get_by_username(username) is not None:
            raise ConflictError(
                "This username is already taken.",
                details={"field": "username", "constraint": "unique"},
            )

        user = User(username=username, email=email, password_hash=self._hasher.hash(password))
        user = self._users.add(user)
        return user, self._tokens.create_access_token(user.id)

    def login(self, *, email: str, password: str) -> tuple[User, str]:
        user = self._users.get_by_email(email)
        if user is None:
            # Constant-time work so timing doesn't reveal whether the email exists.
            self._hasher.verify(password, _dummy_hash(self._hasher))
            raise AuthError("Invalid email or password.")
        if not self._hasher.verify(password, user.password_hash):
            raise AuthError("Invalid email or password.")
        return user, self._tokens.create_access_token(user.id)
