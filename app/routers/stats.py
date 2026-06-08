"""Statistics route (raw-SQL aggregation). Registered before the dynamic
`/{bookmark_id}` route so `/api/bookmarks/stats` is never captured as an id."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, get_stats_service
from app.models import User
from app.schemas.common import ErrorResponse
from app.schemas.stats import StatsResponse
from app.services.stats.interface import IStatsService

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Aggregate statistics for the current user (raw SQL)",
    responses={401: {"model": ErrorResponse, "description": "Authentication required."}},
)
def get_stats(
    current_user: User = Depends(get_current_user),
    service: IStatsService = Depends(get_stats_service),
) -> StatsResponse:
    return StatsResponse(**service.get_stats(user_id=current_user.id))
