"""add optimistic-concurrency version column to bookmarks

Revision ID: 0002_bookmark_version
Revises: 0001_initial
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_bookmark_version"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows default to version 1. `server_default` makes the NOT NULL add
    # safe on a populated table; the ORM manages the value going forward.
    with op.batch_alter_table("bookmarks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("bookmarks") as batch_op:
        batch_op.drop_column("version")
