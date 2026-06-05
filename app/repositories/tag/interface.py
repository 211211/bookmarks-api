"""Tag repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import Tag


class ITagRepository(ABC):
    @abstractmethod
    def get_or_create(self, names: list[str]) -> list[Tag]:
        """Return `Tag` rows for ``names`` (already normalized), creating any
        that don't yet exist. Does not commit — participates in the caller's
        transaction."""
        ...
