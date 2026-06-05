"""Aggregate statistics computed with **raw SQL** (per the assessment brief).

Uses JOIN / GROUP BY / COUNT and a dialect-aware month-bucketing function so the
same code path works on both SQLite and PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _month_expr(dialect: str) -> str:
    """Return a SQL expression that formats ``created_at`` as ``YYYY-MM``."""
    if dialect == "sqlite":
        return "strftime('%Y-%m', created_at)"
    # PostgreSQL (and MySQL via DATE_FORMAT would differ — we target sqlite/pg).
    return "to_char(created_at, 'YYYY-MM')"


def get_stats(db: Session, *, user_id: int) -> dict[str, Any]:
    dialect = db.bind.dialect.name  # type: ignore[union-attr]
    month_expr = _month_expr(dialect)
    params = {"uid": user_id}

    total_bookmarks = db.execute(
        text("SELECT COUNT(*) FROM bookmarks WHERE user_id = :uid"), params
    ).scalar_one()

    total_tags = db.execute(
        text(
            """
            SELECT COUNT(DISTINCT t.id)
            FROM tags t
            JOIN bookmark_tags bt ON bt.tag_id = t.id
            JOIN bookmarks b ON b.id = bt.bookmark_id
            WHERE b.user_id = :uid
            """
        ),
        params,
    ).scalar_one()

    top_tags = db.execute(
        text(
            """
            SELECT t.name AS name, COUNT(*) AS count
            FROM tags t
            JOIN bookmark_tags bt ON bt.tag_id = t.id
            JOIN bookmarks b ON b.id = bt.bookmark_id
            WHERE b.user_id = :uid
            GROUP BY t.id, t.name
            ORDER BY count DESC, t.name ASC
            LIMIT 10
            """
        ),
        params,
    ).mappings().all()

    per_month = db.execute(
        text(
            f"""
            SELECT {month_expr} AS month, COUNT(*) AS count
            FROM bookmarks
            WHERE user_id = :uid
            GROUP BY month
            ORDER BY month ASC
            """
        ),
        params,
    ).mappings().all()

    return {
        "total_bookmarks": int(total_bookmarks or 0),
        "total_tags": int(total_tags or 0),
        "top_tags": [{"name": r["name"], "count": int(r["count"])} for r in top_tags],
        "bookmarks_per_month": [
            {"month": r["month"], "count": int(r["count"])} for r in per_month
        ],
    }
