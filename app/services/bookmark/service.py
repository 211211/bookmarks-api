"""Bookmark service implementation: orchestrates the bookmark + tag repositories,
enforces ownership, and computes pagination."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.core.errors import (
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
)
from app.models import Bookmark
from app.repositories.bookmark.interface import (
    BookmarkFilters,
    IBookmarkRepository,
    StaleVersionError,
)
from app.repositories.tag.interface import ITagRepository
from app.services.bookmark.interface import IBookmarkService
from app.utils.etag.interface import IETagService
from app.utils.tags.interface import ITagNormalizer

MAX_PER_PAGE = 100


class BookmarkService(IBookmarkService):
    def __init__(
        self,
        bookmarks: IBookmarkRepository,
        tags: ITagRepository,
        normalizer: ITagNormalizer,
        etags: IETagService,
    ) -> None:
        self._bookmarks = bookmarks
        self._tags = tags
        self._normalizer = normalizer
        self._etags = etags

    def _check_precondition(self, bookmark: Bookmark, if_match: str | None) -> None:
        """Enforce the `If-Match` optimistic-concurrency precondition for a
        mutation. Missing header -> 428; non-matching version -> 412. Both responses
        carry the current ETag (header + details) so the client can recover."""
        current_etag = self._etags.make_etag(bookmark.version)
        if if_match is None or not if_match.strip():
            raise PreconditionRequiredError(
                "This operation requires an 'If-Match' header with the bookmark's "
                "current ETag to prevent lost updates.",
                details={"header": "If-Match", "current": current_etag},
                headers={"ETag": current_etag},
            )
        if not self._etags.matches(if_match, bookmark.version):
            raise self._conflict(current_etag)

    def _conflict(self, current_etag: str | None) -> PreconditionFailedError:
        """Build a uniform 412 (in-process mismatch or DB-level race)."""
        details = {"expected": current_etag} if current_etag else None
        headers = {"ETag": current_etag} if current_etag else None
        return PreconditionFailedError(
            "The bookmark was modified by another request. Re-fetch it and retry "
            "with the latest ETag.",
            details=details,
            headers=headers,
        )

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

    def update(
        self,
        *,
        user_id: int,
        bookmark_id: int,
        changes: dict[str, Any],
        if_match: str | None,
    ) -> Bookmark:
        bookmark = self.get(user_id=user_id, bookmark_id=bookmark_id)
        self._check_precondition(bookmark, if_match)
        # Resolve tags FIRST — get_or_create may flush to assign new tag PKs, and
        # we don't want that intermediate flush to persist (and version-bump) a
        # half-applied change. Apply all mutations together just before commit.
        new_tags = None
        if "tags" in changes and changes["tags"] is not None:
            new_tags = self._tags.get_or_create(self._normalizer.normalize(changes["tags"]))
        if "url" in changes:
            bookmark.url = changes["url"]
        if "title" in changes:
            bookmark.title = changes["title"]
        if "description" in changes:
            bookmark.description = changes["description"]
        if new_tags is not None:
            bookmark.tags = new_tags
        try:
            return self._bookmarks.update(bookmark)
        except StaleVersionError as exc:
            raise self._conflict(self._current_etag(user_id, bookmark_id)) from exc

    def delete(self, *, user_id: int, bookmark_id: int, if_match: str | None) -> None:
        bookmark = self.get(user_id=user_id, bookmark_id=bookmark_id)
        self._check_precondition(bookmark, if_match)
        try:
            self._bookmarks.delete(bookmark)
        except StaleVersionError as exc:
            raise self._conflict(self._current_etag(user_id, bookmark_id)) from exc

    def _current_etag(self, user_id: int, bookmark_id: int) -> str | None:
        """Re-read the (post-rollback) current version so a race-conflict 412 can
        report the latest ETag. Returns None if the row was deleted concurrently."""
        current = self._bookmarks.get_owned(user_id, bookmark_id)
        return self._etags.make_etag(current.version) if current is not None else None
