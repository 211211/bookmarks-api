"""Association tables for many-to-many relationships."""

from sqlalchemy import Column, ForeignKey, Table

from app.database import Base

# Many-to-many link between bookmarks and tags.
# Composite primary key (bookmark_id, tag_id) prevents duplicate links and both
# foreign keys cascade on delete so removing a bookmark or tag cleans up links.
bookmark_tags = Table(
    "bookmark_tags",
    Base.metadata,
    Column(
        "bookmark_id",
        ForeignKey("bookmarks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "tag_id",
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)
