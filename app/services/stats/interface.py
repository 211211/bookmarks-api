"""Stats service interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IStatsService(ABC):
    @abstractmethod
    def get_stats(self, *, user_id: int) -> dict[str, Any]: ...
