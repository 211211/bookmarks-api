"""Tag normalization logic (shared by the schema layer and the service layer)."""

from __future__ import annotations

from app.utils.tags.interface import ITagNormalizer

MAX_TAG_LENGTH = 50
MAX_TAGS_PER_BOOKMARK = 30


def normalize_tags(raw: list[str] | None) -> list[str]:
    """Normalize a list of tag names: trim, lowercase, drop blanks, de-duplicate
    while preserving order. Raises ``ValueError`` for invalid tags so callers get
    a clean 422 validation error."""
    if not raw:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("Each tag must be a string.")
        name = item.strip().lower()
        if not name:
            continue
        if len(name) > MAX_TAG_LENGTH:
            raise ValueError(f"Tag '{name[:20]}…' exceeds {MAX_TAG_LENGTH} characters.")
        if name not in seen:
            seen.add(name)
            normalized.append(name)

    if len(normalized) > MAX_TAGS_PER_BOOKMARK:
        raise ValueError(f"A bookmark may have at most {MAX_TAGS_PER_BOOKMARK} tags.")
    return normalized


class TagNormalizer(ITagNormalizer):
    """Default `ITagNormalizer` backed by :func:`normalize_tags`."""

    def normalize(self, raw: list[str] | None) -> list[str]:
        return normalize_tags(raw)
