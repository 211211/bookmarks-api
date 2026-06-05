"""User repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import User


class IUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def add(self, user: User) -> User:
        """Persist a new user and return it (with id/created_at populated)."""
        ...
