"""Bookmark data-access: CRUD plus search/filter/pagination.

Every function is scoped by ``user_id`` so a user can only ever touch their own
bookmarks. Lookups for a non-owned id return ``NotFoundError`` (404) rather than
403, so the API never reveals that another user's bookmark exists.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.errors import NotFoundError
from app.crud.tags import get_or_create_tags
from app.models import Bookmark, Tag

# Whitelisted sort fields (prevents arbitrary column injection via the API).
_SORT_FIELDS = {
    "created_at": Bookmark.created_at,
    "updated_at": Bookmark.updated_at,
    "title": Bookmark.title,
    "id": Bookmark.id,
}

MAX_PER_PAGE = 100


def create_bookmark(
    db: Session,
    *,
    user_id: int,
    url: str,
    title: str,
    description: str | None,
    tag_names: list[str],
) -> Bookmark:
    bookmark = Bookmark(url=url, title=title, description=description, user_id=user_id)
    bookmark.tags = get_or_create_tags(db, tag_names)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


def get_owned_bookmark(db: Session, *, user_id: int, bookmark_id: int) -> Bookmark:
    bookmark = db.scalar(
        select(Bookmark).where(Bookmark.id == bookmark_id, Bookmark.user_id == user_id)
    )
    if bookmark is None:
        raise NotFoundError(
            "Bookmark not found.", details={"field": "id", "value": bookmark_id}
        )
    return bookmark


def update_bookmark(db: Session, *, bookmark: Bookmark, changes: dict[str, Any]) -> Bookmark:
    """Apply only the fields present in ``changes`` (partial update)."""
    if "url" in changes:
        bookmark.url = changes["url"]
    if "title" in changes:
        bookmark.title = changes["title"]
    if "description" in changes:
        bookmark.description = changes["description"]
    if "tags" in changes and changes["tags"] is not None:
        bookmark.tags = get_or_create_tags(db, changes["tags"])
    db.commit()
    db.refresh(bookmark)
    return bookmark


def delete_bookmark(db: Session, *, bookmark: Bookmark) -> None:
    db.delete(bookmark)
    db.commit()


def _apply_filters(
    stmt: Select,
    *,
    user_id: int,
    tag: str | None,
    q: str | None,
    date_from: date | None,
    date_to: date | None,
    join_tags: bool,
) -> Select:
    if join_tags:
        stmt = stmt.join(Bookmark.tags)
    stmt = stmt.where(Bookmark.user_id == user_id)
    if tag:
        stmt = stmt.where(Tag.name == tag.strip().lower())
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Bookmark.title).like(like),
                func.lower(Bookmark.description).like(like),
            )
        )
    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        stmt = stmt.where(Bookmark.created_at >= start)
    if date_to:
        end = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        stmt = stmt.where(Bookmark.created_at <= end)
    return stmt


def list_bookmarks(
    db: Session,
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
    """List a user's bookmarks with optional filtering and pagination.

    Returns a dict with ``items`` and pagination metadata. Supports both
    offset pagination (``page``/``per_page``) and keyset/cursor pagination
    (``cursor``) — when a cursor is supplied, results are ordered by id descending.
    """
    per_page = max(1, min(per_page, MAX_PER_PAGE))
    join_tags = tag is not None

    filter_kwargs = dict(
        user_id=user_id, tag=tag, q=q, date_from=date_from, date_to=date_to, join_tags=join_tags
    )

    # Total count (DISTINCT guards against row fan-out from the tag join).
    count_stmt = _apply_filters(
        select(func.count(func.distinct(Bookmark.id))).select_from(Bookmark), **filter_kwargs
    )
    total = db.scalar(count_stmt) or 0

    data_stmt = _apply_filters(select(Bookmark), **filter_kwargs)

    if cursor is not None:
        # Keyset pagination: stable, efficient, no large OFFSET scans.
        data_stmt = (
            data_stmt.where(Bookmark.id < cursor)
            .order_by(Bookmark.id.desc())
            .limit(per_page)
        )
        items = list(db.scalars(data_stmt).unique().all())
        next_cursor = items[-1].id if len(items) == per_page else None
        return {
            "items": items,
            "page": 1,
            "per_page": per_page,
            "total": total,
            "total_pages": math.ceil(total / per_page) if total else 0,
            "has_next": next_cursor is not None,
            "has_prev": False,
            "next_cursor": next_cursor,
        }

    # Offset pagination.
    field = sort.lstrip("-")
    column = _SORT_FIELDS.get(field, Bookmark.created_at)
    direction = desc if sort.startswith("-") else asc
    data_stmt = (
        data_stmt.order_by(direction(column), Bookmark.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = list(db.scalars(data_stmt).unique().all())
    total_pages = math.ceil(total / per_page) if total else 0
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "next_cursor": None,
    }
