"""Login-guard interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ILoginGuard(ABC):
    """Tracks failed login attempts per account and locks it out after too many,
    independent of source IP (so distributed credential-stuffing against one
    account is bounded)."""

    @abstractmethod
    def assert_not_locked(self, identifier: str) -> None:
        """Raise ``TooManyAttemptsError`` (429) if the account is currently locked."""
        ...

    @abstractmethod
    def record_failure(self, identifier: str) -> None:
        """Record a failed attempt; lock the account when the threshold is hit."""
        ...

    @abstractmethod
    def record_success(self, identifier: str) -> None:
        """Clear the failure state after a successful login."""
        ...
