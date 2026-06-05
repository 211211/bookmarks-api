"""Tag data-access: get-or-create normalized tags in a single round trip."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tag


def get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    """Return `Tag` rows for ``names`` (assumed already normalized/lowercased),
    creating any that don't yet exist. Existing tags are fetched in one query to
    avoid N+1."""
    if not names:
        return []

    existing = db.scalars(select(Tag).where(Tag.name.in_(names))).all()
    by_name: dict[str, Tag] = {tag.name: tag for tag in existing}

    result: list[Tag] = []
    for name in names:
        tag = by_name.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()  # assign PK and enforce uniqueness now
            by_name[name] = tag
        result.append(tag)
    return result
