"""Auth service interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import User


class IAuthService(ABC):
    @abstractmethod
    def register(self, *, username: str, email: str, password: str) -> tuple[User, str]:
        """Create a user and return ``(user, access_token)``."""
        ...

    @abstractmethod
    def login(self, *, email: str, password: str) -> tuple[User, str]:
        """Authenticate and return ``(user, access_token)``."""
        ...
