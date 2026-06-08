"""Interfaces for the security helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IPasswordHasher(ABC):
    """Hashes and verifies passwords (one-way, salted — never reversible)."""

    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, password_hash: str) -> bool: ...


class ITokenProvider(ABC):
    """Issues and verifies signed access tokens."""

    @abstractmethod
    def create_access_token(
        self, subject: int | str, expires_minutes: int | None = None
    ) -> str: ...

    @abstractmethod
    def decode(self, token: str) -> dict:
        """Decode and verify a token, returning its claims. Raises on failure."""
        ...
