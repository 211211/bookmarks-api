"""Tag schema helpers.

The normalization logic now lives in ``app.utils.tags.normalizer`` (behind the
``ITagNormalizer`` interface). It is re-exported here so the schema validators in
``app.schemas.bookmark`` keep a stable import path.
"""

from app.utils.tags.normalizer import (
    MAX_TAG_LENGTH,
    MAX_TAGS_PER_BOOKMARK,
    normalize_tags,
)

__all__ = ["normalize_tags", "MAX_TAG_LENGTH", "MAX_TAGS_PER_BOOKMARK"]
