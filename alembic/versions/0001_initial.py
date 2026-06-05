"""initial schema: users, tags, bookmarks, bookmark_tags

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
    )
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    op.create_table(
        "bookmarks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_bookmarks_user_id", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_bookmarks_user_id", "bookmarks", ["user_id"])
    op.create_index("ix_bookmarks_created_at", "bookmarks", ["created_at"])

    op.create_table(
        "bookmark_tags",
        sa.Column("bookmark_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bookmark_id"], ["bookmarks.id"], name="fk_bt_bookmark_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="fk_bt_tag_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("bookmark_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("bookmark_tags")
    op.drop_index("ix_bookmarks_created_at", table_name="bookmarks")
    op.drop_index("ix_bookmarks_user_id", table_name="bookmarks")
    op.drop_table("bookmarks")
    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
