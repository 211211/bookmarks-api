"""Interface for the ETag service."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IETagService(ABC):
    """Formats entity-tag headers and matches client `If-Match` values against a
    resource's current version (RFC 7232 strong comparison)."""

    @abstractmethod
    def make_etag(self, version: int) -> str:
        """Return the strong ETag header value for a given version, e.g. ``"3"``."""
        ...

    @abstractmethod
    def matches(self, if_match_header: str, version: int) -> bool:
        """Return True if ``if_match_header`` (a non-empty `If-Match` value — a
        strong ETag, a comma-separated list, or ``*``) matches ``version``."""
        ...
