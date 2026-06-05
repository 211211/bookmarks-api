"""Statistics route (raw-SQL aggregation). Registered before the dynamic
`/{bookmark_id}` route so `/api/bookmarks/stats` is never captured as an id."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.crud import stats as crud
from app.database import get_db
from app.models import User
from app.schemas.common import ErrorResponse
from app.schemas.stats import StatsResponse

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Aggregate statistics for the current user (raw SQL)",
    responses={401: {"model": ErrorResponse, "description": "Authentication required."}},
)
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatsResponse:
    data = crud.get_stats(db, user_id=current_user.id)
    return StatsResponse(**data)
