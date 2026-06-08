"""Bookmark model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import bookmark_tags


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 2083 matches the max length Pydantic's HttpUrl accepts, so a value that
    # passes validation always fits the column (avoids a PostgreSQL write error).
    url: Mapped[str] = mapped_column(String(2083), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Optimistic-concurrency version. Managed by SQLAlchemy's `version_id_col`
    # (see __mapper_args__): set to 1 on insert, auto-incremented on every UPDATE,
    # and added to the UPDATE/DELETE WHERE clause so a concurrent write that
    # changed the row raises StaleDataError instead of silently clobbering it.
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    # Enable SQLAlchemy version-counter optimistic locking on this column.
    __mapper_args__ = {"version_id_col": version}

    # Composite index for the common access pattern: list a user's bookmarks
    # ordered by recency (WHERE user_id = ? ORDER BY created_at DESC).
    __table_args__ = (Index("ix_bookmarks_user_created", "user_id", "created_at"),)

    owner: Mapped["User"] = relationship(back_populates="bookmarks")  # noqa: F821
    # `selectin` batch-loads tags for a page of bookmarks in one extra query,
    # avoiding the N+1 problem when serializing a list.
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        secondary=bookmark_tags,
        back_populates="bookmarks",
        lazy="selectin",
        order_by="Tag.name",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Bookmark id={self.id} title={self.title!r} user_id={self.user_id}>"
