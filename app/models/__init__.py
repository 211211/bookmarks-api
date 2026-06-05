"""ORM models. Importing this package registers every table on `Base.metadata`
so that Alembic autogeneration and `create_all` see the full schema."""

from app.models.associations import bookmark_tags
from app.models.bookmark import Bookmark
from app.models.tag import Tag
from app.models.user import User

__all__ = ["User", "Bookmark", "Tag", "bookmark_tags"]
