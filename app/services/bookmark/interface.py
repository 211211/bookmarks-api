"""Bookmark service interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from app.models import Bookmark


class IBookmarkService(ABC):
    @abstractmethod
    def create(
        self,
        *,
        user_id: int,
        url: str,
        title: str,
        description: str | None,
        tags: list[str],
    ) -> Bookmark: ...

    @abstractmethod
    def get(self, *, user_id: int, bookmark_id: int) -> Bookmark:
        """Return an owned bookmark or raise ``NotFoundError``."""
        ...

    @abstractmethod
    def list(
        self,
        *,
        user_id: int,
        tag: str | None = None,
        q: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "-created_at",
        cursor: int | None = None,
    ) -> dict[str, Any]:
        """Return ``{"items": [...], + pagination metadata}``."""
        ...

    @abstractmethod
    def update(self, *, user_id: int, bookmark_id: int, changes: dict[str, Any]) -> Bookmark: ...

    @abstractmethod
    def delete(self, *, user_id: int, bookmark_id: int) -> None: ...
