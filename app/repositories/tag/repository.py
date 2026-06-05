"""SQLAlchemy implementation of the tag repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tag
from app.repositories.tag.interface import ITagRepository


class TagRepository(ITagRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create(self, names: list[str]) -> list[Tag]:
        if not names:
            return []

        existing = self._db.scalars(select(Tag).where(Tag.name.in_(names))).all()
        by_name: dict[str, Tag] = {tag.name: tag for tag in existing}

        result: list[Tag] = []
        for name in names:
            tag = by_name.get(name)
            if tag is None:
                tag = Tag(name=name)
                self._db.add(tag)
                self._db.flush()  # assign PK + enforce uniqueness within the txn
                by_name[name] = tag
            result.append(tag)
        return result
