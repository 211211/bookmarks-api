"""widen bookmarks.url to 2083 and add (user_id, created_at) composite index

Revision ID: 0003_url_len_and_index
Revises: 0002_bookmark_version
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_url_len_and_index"
down_revision: str | None = "0002_bookmark_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("bookmarks") as batch_op:
        batch_op.alter_column(
            "url",
            existing_type=sa.String(length=2048),
            type_=sa.String(length=2083),
            existing_nullable=False,
        )
    op.create_index(
        "ix_bookmarks_user_created", "bookmarks", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_bookmarks_user_created", table_name="bookmarks")
    with op.batch_alter_table("bookmarks") as batch_op:
        batch_op.alter_column(
            "url",
            existing_type=sa.String(length=2083),
            type_=sa.String(length=2048),
            existing_nullable=False,
        )
