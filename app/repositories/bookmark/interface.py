"""Bookmark repository interface + the filter value object."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from app.models import Bookmark


class StaleVersionError(Exception):
    """Raised by a repository when a write loses an optimistic-locking race
    (the row's version changed between load and commit). The service layer
    translates this into a 412 Precondition Failed."""


@dataclass(frozen=True)
class BookmarkFilters:
    """Immutable set of list/search filters passed to the repository."""

    tag: str | None = None
    q: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class IBookmarkRepository(ABC):
    @abstractmethod
    def add(self, bookmark: Bookmark) -> Bookmark: ...

    @abstractmethod
    def get_owned(self, user_id: int, bookmark_id: int) -> Bookmark | None: ...

    @abstractmethod
    def update(self, bookmark: Bookmark) -> Bookmark:
        """Persist changes made to an already-loaded bookmark."""
        ...

    @abstractmethod
    def delete(self, bookmark: Bookmark) -> None: ...

    @abstractmethod
    def count(self, user_id: int, filters: BookmarkFilters) -> int: ...

    @abstractmethod
    def list_offset(
        self, user_id: int, filters: BookmarkFilters, *, sort: str, limit: int, offset: int
    ) -> list[Bookmark]: ...

    @abstractmethod
    def list_keyset(
        self, user_id: int, filters: BookmarkFilters, *, cursor: int, limit: int
    ) -> list[Bookmark]:
        """Keyset pagination ordered by id descending (id < cursor)."""
        ...
