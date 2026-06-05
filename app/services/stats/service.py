"""Stats service implementation."""

from __future__ import annotations

from typing import Any

from app.repositories.stats.interface import IStatsRepository
from app.services.stats.interface import IStatsService


class StatsService(IStatsService):
    def __init__(self, stats: IStatsRepository) -> None:
        self._stats = stats

    def get_stats(self, *, user_id: int) -> dict[str, Any]:
        return self._stats.get_stats(user_id)
