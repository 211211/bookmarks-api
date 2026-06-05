"""Bookmark service implementation: orchestrates the bookmark + tag repositories,
enforces ownership, and computes pagination."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.core.errors import NotFoundError
from app.models import Bookmark
from app.repositories.bookmark.interface import BookmarkFilters, IBookmarkRepository
from app.repositories.tag.interface import ITagRepository
from app.services.bookmark.interface import IBookmarkService
from app.utils.tags.interface import ITagNormalizer

MAX_PER_PAGE = 100


class BookmarkService(IBookmarkService):
    def __init__(
        self,
        bookmarks: IBookmarkRepository,
        tags: ITagRepository,
        normalizer: ITagNormalizer,
    ) -> None:
        self._bookmarks = bookmarks
        self._tags = tags
        self._normalizer = normalizer

    def create(
        self,
        *,
        user_id: int,
        url: str,
        title: str,
        description: str | None,
        tags: list[str],
    ) -> Bookmark:
        tag_objs = self._tags.get_or_create(self._normalizer.normalize(tags))
        bookmark = Bookmark(url=url, title=title, description=description, user_id=user_id)
        bookmark.tags = tag_objs
        return self._bookmarks.add(bookmark)

    def get(self, *, user_id: int, bookmark_id: int) -> Bookmark:
        bookmark = self._bookmarks.get_owned(user_id, bookmark_id)
        if bookmark is None:
            raise NotFoundError(
                "Bookmark not found.", details={"field": "id", "value": bookmark_id}
            )
        return bookmark

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
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        filters = BookmarkFilters(tag=tag, q=q, date_from=date_from, date_to=date_to)
        total = self._bookmarks.count(user_id, filters)
        total_pages = math.ceil(total / per_page) if total else 0

        if cursor is not None:
            # Fetch one extra row to know whether a further page genuinely exists.
            rows = self._bookmarks.list_keyset(user_id, filters, cursor=cursor, limit=per_page + 1)
            has_more = len(rows) > per_page
            items = rows[:per_page]
            next_cursor = items[-1].id if (has_more and items) else None
            return {
                "items": items,
                "page": 1,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_more,
                "has_prev": False,
                "next_cursor": next_cursor,
            }

        items = self._bookmarks.list_offset(
            user_id, filters, sort=sort, limit=per_page, offset=(page - 1) * per_page
        )
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

    def update(self, *, user_id: int, bookmark_id: int, changes: dict[str, Any]) -> Bookmark:
        bookmark = self.get(user_id=user_id, bookmark_id=bookmark_id)
        if "url" in changes:
            bookmark.url = changes["url"]
        if "title" in changes:
            bookmark.title = changes["title"]
        if "description" in changes:
            bookmark.description = changes["description"]
        if "tags" in changes and changes["tags"] is not None:
            bookmark.tags = self._tags.get_or_create(self._normalizer.normalize(changes["tags"]))
        return self._bookmarks.update(bookmark)

    def delete(self, *, user_id: int, bookmark_id: int) -> None:
        bookmark = self.get(user_id=user_id, bookmark_id=bookmark_id)
        self._bookmarks.delete(bookmark)
