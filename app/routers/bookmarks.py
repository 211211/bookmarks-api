"""Bookmark routes: CRUD + search/filter/pagination. All scoped to the
authenticated user via the `get_current_user` dependency."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.crud import bookmarks as crud
from app.database import get_db
from app.models import User
from app.schemas.bookmark import BookmarkCreate, BookmarkOut, BookmarkPage, BookmarkUpdate
from app.schemas.common import ErrorResponse, PageMeta

# Error responses shared across the authenticated bookmark routes.
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
    db: Session = Depends(get_db),
) -> BookmarkOut:
    bookmark = crud.create_bookmark(
        db,
        user_id=current_user.id,
        url=str(payload.url),
        title=payload.title,
        description=payload.description,
        tag_names=payload.tags,
    )
    return BookmarkOut.model_validate(bookmark)


@router.get(
    "",
    response_model=BookmarkPage,
    summary="List, search, and filter bookmarks",
)
def list_bookmarks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    tag: str | None = Query(None, description="Filter by exact tag name."),
    q: str | None = Query(None, description="Keyword searched in title and description."),
    date_from: date | None = Query(
        None, alias="from", description="Created on or after this date (YYYY-MM-DD)."
    ),
    date_to: date | None = Query(
        None, alias="to", description="Created on or before this date (YYYY-MM-DD)."
    ),
    page: int = Query(1, ge=1, description="1-based page number (offset pagination)."),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)."),
    sort: str = Query(
        "-created_at",
        description="Sort field: created_at | updated_at | title | id. Prefix '-' for descending.",
    ),
    cursor: int | None = Query(
        None, ge=1, description="Keyset cursor for cursor-based pagination (bonus)."
    ),
) -> BookmarkPage:
    result = crud.list_bookmarks(
        db,
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
    db: Session = Depends(get_db),
) -> BookmarkOut:
    bookmark = crud.get_owned_bookmark(db, user_id=current_user.id, bookmark_id=bookmark_id)
    return BookmarkOut.model_validate(bookmark)


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
    db: Session = Depends(get_db),
) -> BookmarkOut:
    bookmark = crud.get_owned_bookmark(db, user_id=current_user.id, bookmark_id=bookmark_id)

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

    bookmark = crud.update_bookmark(db, bookmark=bookmark, changes=changes)
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
    db: Session = Depends(get_db),
) -> Response:
    bookmark = crud.get_owned_bookmark(db, user_id=current_user.id, bookmark_id=bookmark_id)
    crud.delete_bookmark(db, bookmark=bookmark)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
