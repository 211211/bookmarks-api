"""Stats repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IStatsRepository(ABC):
    @abstractmethod
    def get_stats(self, user_id: int) -> dict[str, Any]:
        """Aggregate per-user statistics (computed with raw SQL)."""
        ...
