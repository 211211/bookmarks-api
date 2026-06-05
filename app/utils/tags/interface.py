"""Interface for the tag normalizer."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ITagNormalizer(ABC):
    @abstractmethod
    def normalize(self, raw: list[str] | None) -> list[str]:
        """Trim, lowercase, drop blanks, and de-duplicate tag names.
        Raises ``ValueError`` on invalid input."""
        ...
