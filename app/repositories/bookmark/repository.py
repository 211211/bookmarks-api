"""SQLAlchemy implementation of the bookmark repository."""

from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models import Bookmark, Tag
from app.repositories.bookmark.interface import BookmarkFilters, IBookmarkRepository

# Whitelisted sort fields (prevents arbitrary column injection via the API).
_SORT_FIELDS = {
    "created_at": Bookmark.created_at,
    "updated_at": Bookmark.updated_at,
    "title": Bookmark.title,
    "id": Bookmark.id,
}


class BookmarkRepository(IBookmarkRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── writes ─────────────────────────────────────────────────────────────
    def add(self, bookmark: Bookmark) -> Bookmark:
        self._db.add(bookmark)
        self._db.commit()
        self._db.refresh(bookmark)
        return bookmark

    def get_owned(self, user_id: int, bookmark_id: int) -> Bookmark | None:
        return self._db.scalar(
            select(Bookmark).where(Bookmark.id == bookmark_id, Bookmark.user_id == user_id)
        )

    def update(self, bookmark: Bookmark) -> Bookmark:
        self._db.commit()
        self._db.refresh(bookmark)
        return bookmark

    def delete(self, bookmark: Bookmark) -> None:
        self._db.delete(bookmark)
        self._db.commit()

    # ── reads ──────────────────────────────────────────────────────────────
    def count(self, user_id: int, filters: BookmarkFilters) -> int:
        stmt = self._apply_filters(
            select(func.count(func.distinct(Bookmark.id))).select_from(Bookmark),
            user_id,
            filters,
        )
        return self._db.scalar(stmt) or 0

    def list_offset(
        self, user_id: int, filters: BookmarkFilters, *, sort: str, limit: int, offset: int
    ) -> list[Bookmark]:
        field = sort.lstrip("-")
        column = _SORT_FIELDS.get(field, Bookmark.created_at)
        direction = desc if sort.startswith("-") else asc
        stmt = self._apply_filters(select(Bookmark), user_id, filters)
        stmt = stmt.order_by(direction(column), Bookmark.id.desc()).offset(offset).limit(limit)
        return list(self._db.scalars(stmt).unique().all())

    def list_keyset(
        self, user_id: int, filters: BookmarkFilters, *, cursor: int, limit: int
    ) -> list[Bookmark]:
        stmt = self._apply_filters(select(Bookmark), user_id, filters)
        stmt = stmt.where(Bookmark.id < cursor).order_by(Bookmark.id.desc()).limit(limit)
        return list(self._db.scalars(stmt).unique().all())

    # ── helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _apply_filters(stmt: Select, user_id: int, filters: BookmarkFilters) -> Select:
        if filters.tag:
            stmt = stmt.join(Bookmark.tags)
        stmt = stmt.where(Bookmark.user_id == user_id)
        if filters.tag:
            stmt = stmt.where(Tag.name == filters.tag.strip().lower())
        if filters.q:
            # Escape LIKE wildcards so a literal '%'/'_' isn't a metacharacter.
            term = filters.q.strip().lower()
            term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{term}%"
            stmt = stmt.where(
                or_(
                    func.lower(Bookmark.title).like(like, escape="\\"),
                    func.lower(Bookmark.description).like(like, escape="\\"),
                )
            )
        if filters.date_from:
            start = datetime.combine(filters.date_from, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(Bookmark.created_at >= start)
        if filters.date_to:
            end = datetime.combine(filters.date_to, time.max, tzinfo=timezone.utc)
            stmt = stmt.where(Bookmark.created_at <= end)
        return stmt
