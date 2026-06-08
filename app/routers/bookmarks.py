"""Bookmark routes: CRUD + search/filter/pagination. All scoped to the
authenticated user; business logic lives in the bookmark service."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import get_bookmark_service, get_current_user
from app.models import User
from app.schemas.bookmark import BookmarkCreate, BookmarkOut, BookmarkPage, BookmarkUpdate
from app.schemas.common import ErrorResponse, PageMeta
from app.services.bookmark.interface import IBookmarkService

_AUTH_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Authentication required."},
}
_NOT_FOUND = {404: {"model": ErrorResponse, "description": "Bookmark not found."}}
_VALIDATION = {422: {"model": ErrorResponse, "description": "Validation error."}}

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"], responses=_AUTH_RESPONSES)


def _to_page(result: dict) -> BookmarkPage:
    return BookmarkPage(
        items=[BookmarkOut.model_validate(b) for b in result["items"]],
        pagination=PageMeta(
            page=result["page"],
            per_page=result["per_page"],
            total=result["total"],
            total_pages=result["total_pages"],
            has_next=result["has_next"],
            has_prev=result["has_prev"],
            next_cursor=result["next_cursor"],
        ),
    )


@router.post(
    "",
    response_model=BookmarkOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bookmark",
    responses={**_VALIDATION},
)
def create_bookmark(
    payload: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    service: IBookmarkService = Depends(get_bookmark_service),
) -> BookmarkOut:
    bookmark = service.create(
        user_id=current_user.id,
        url=str(payload.url),
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
    )
    return BookmarkOut.model_validate(bookmark)


@router.get(
    "",
    response_model=BookmarkPage,
    summary="List, search, and filter bookmarks",
)
def list_bookmarks(
    current_user: User = Depends(get_current_user),
    service: IBookmarkService = Depends(get_bookmark_service),
    tag: str | None = Query(None, description="Filter by exact tag name."),
    q: str | None = Query(None, description="Keyword searched in title and description."),
    date_from: date | None = Query(
        None,
        alias="from",
        description="Created on or after this date (YYYY-MM-DD, UTC, inclusive).",
    ),
    date_to: date | None = Query(
        None,
        alias="to",
        description="Created on or before this date (YYYY-MM-DD, UTC, inclusive).",
    ),
    page: int = Query(1, ge=1, description="1-based page number (offset pagination)."),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)."),
    sort: str = Query(
        "-created_at",
        description="Sort field: created_at | updated_at | title | id. Prefix '-' for descending.",
    ),
    cursor: int | None = Query(
        None,
        ge=1,
        description="Keyset cursor (bonus). When set, results are ordered by id "
        "descending and `sort` is ignored; follow `next_cursor` for the next page.",
    ),
) -> BookmarkPage:
    result = service.list(
        user_id=current_user.id,
        tag=tag,
        q=q,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
        sort=sort,
        cursor=cursor,
    )
    return _to_page(result)


@router.get(
    "/{bookmark_id}",
    response_model=BookmarkOut,
    summary="Retrieve a single bookmark",
    responses={**_NOT_FOUND},
)
def get_bookmark(
    bookmark_id: int,
    current_user: User = Depends(get_current_user),
    service: IBookmarkService = Depends(get_bookmark_service),
) -> BookmarkOut:
    return BookmarkOut.model_validate(
        service.get(user_id=current_user.id, bookmark_id=bookmark_id)
    )


@router.put(
    "/{bookmark_id}",
    response_model=BookmarkOut,
    summary="Update a bookmark",
    responses={**_NOT_FOUND, **_VALIDATION},
)
def update_bookmark(
    bookmark_id: int,
    payload: BookmarkUpdate,
    current_user: User = Depends(get_current_user),
    service: IBookmarkService = Depends(get_bookmark_service),
) -> BookmarkOut:
    fields = payload.model_fields_set
    changes: dict = {}
    if "url" in fields and payload.url is not None:
        changes["url"] = str(payload.url)
    if "title" in fields and payload.title is not None:
        changes["title"] = payload.title
    if "description" in fields:
        changes["description"] = payload.description  # may be set to null to clear
    if "tags" in fields and payload.tags is not None:
        changes["tags"] = payload.tags

    bookmark = service.update(user_id=current_user.id, bookmark_id=bookmark_id, changes=changes)
    return BookmarkOut.model_validate(bookmark)


@router.delete(
    "/{bookmark_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a bookmark",
    responses={**_NOT_FOUND},
)
def delete_bookmark(
    bookmark_id: int,
    current_user: User = Depends(get_current_user),
    service: IBookmarkService = Depends(get_bookmark_service),
) -> Response:
    service.delete(user_id=current_user.id, bookmark_id=bookmark_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
