"""Tag model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import bookmark_tags


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Names are normalized to lowercase before insertion (see crud.tags).
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    bookmarks: Mapped[list["Bookmark"]] = relationship(  # noqa: F821
        secondary=bookmark_tags,
        back_populates="tags",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Tag id={self.id} name={self.name!r}>"
