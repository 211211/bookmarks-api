"""Populate the database with realistic sample data (bonus).

Run with the schema already migrated::

    python -m scripts.seed

Idempotent: it does nothing if any users already exist (pass --reset to wipe
the bookmark/user data first).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from app.core.security import hash_password
from app.crud.tags import get_or_create_tags
from app.database import SessionLocal
from app.models import Bookmark, Tag, User
from app.models.associations import bookmark_tags

SEED_PASSWORD = "password123"

# (title, url, description, [tags], created_at) for user "alice".
ALICE_BOOKMARKS = [
    ("FastAPI docs", "https://fastapi.tiangolo.com/", "The official FastAPI documentation.",
     ["python", "fastapi", "backend"], datetime(2025, 1, 8, 9, 0, tzinfo=timezone.utc)),
    ("SQLAlchemy 2.0 ORM", "https://docs.sqlalchemy.org/en/20/orm/", "Typed ORM guide.",
     ["python", "sql", "orm"], datetime(2025, 1, 19, 14, 30, tzinfo=timezone.utc)),
    ("Use The Index, Luke", "https://use-the-index-luke.com/", "SQL indexing & performance.",
     ["sql", "performance"], datetime(2025, 1, 27, 11, 0, tzinfo=timezone.utc)),
    ("PyJWT", "https://pyjwt.readthedocs.io/", "JWT in Python.",
     ["python", "auth", "security"], datetime(2025, 2, 3, 8, 15, tzinfo=timezone.utc)),
    ("REST API design", "https://restfulapi.net/", "RESTful conventions.",
     ["backend", "api", "design"], datetime(2025, 2, 14, 16, 45, tzinfo=timezone.utc)),
    ("Twelve-Factor App", "https://12factor.net/", "Methodology for SaaS apps.",
     ["backend", "design", "devops"], datetime(2025, 2, 22, 10, 5, tzinfo=timezone.utc)),
    ("pytest docs", "https://docs.pytest.org/", "Testing framework.",
     ["python", "testing"], datetime(2025, 3, 4, 13, 0, tzinfo=timezone.utc)),
    ("OpenAPI spec", "https://spec.openapis.org/oas/latest.html", "OpenAPI 3.1 specification.",
     ["api", "design", "openapi"], datetime(2025, 3, 12, 9, 30, tzinfo=timezone.utc)),
    ("Alembic tutorial", "https://alembic.sqlalchemy.org/en/latest/tutorial.html", "DB migrations.",
     ["python", "sql", "migrations"], datetime(2025, 3, 20, 15, 20, tzinfo=timezone.utc)),
    ("bcrypt", "https://github.com/pyca/bcrypt", "Password hashing.",
     ["python", "auth", "security"], datetime(2025, 4, 2, 12, 0, tzinfo=timezone.utc)),
    ("Podman docs", "https://docs.podman.io/", "Daemonless containers.",
     ["devops", "containers"], datetime(2025, 4, 9, 17, 10, tzinfo=timezone.utc)),
    ("PostgreSQL docs", "https://www.postgresql.org/docs/", "The Postgres manual.",
     ["sql", "postgres", "backend"], datetime(2025, 4, 18, 8, 40, tzinfo=timezone.utc)),
]

# Bookmarks for user "bob" (used to prove ownership isolation).
BOB_BOOKMARKS = [
    ("Bob's reading list", "https://example.com/bob", "Private to bob.",
     ["personal"], datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc)),
    ("Rust book", "https://doc.rust-lang.org/book/", "Learning Rust.",
     ["rust", "tutorial"], datetime(2025, 4, 1, 10, 0, tzinfo=timezone.utc)),
]


def _create_user(db, username: str, email: str) -> User:
    user = User(username=username, email=email, password_hash=hash_password(SEED_PASSWORD))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_bookmarks(db, user: User, rows) -> None:
    for title, url, description, tags, created in rows:
        bookmark = Bookmark(
            url=url,
            title=title,
            description=description,
            user_id=user.id,
            created_at=created,
            updated_at=created,
        )
        bookmark.tags = get_or_create_tags(db, tags)
        db.add(bookmark)
    db.commit()


def _reset(db) -> None:
    db.execute(bookmark_tags.delete())
    db.query(Bookmark).delete()
    db.query(Tag).delete()
    db.query(User).delete()
    db.commit()


def seed(reset: bool = False) -> None:
    db = SessionLocal()
    try:
        if reset:
            _reset(db)
        if db.query(User).count() > 0:
            print("Database already contains users — skipping. Use --reset to wipe and reseed.")
            return

        alice = _create_user(db, "alice", "alice@example.com")
        bob = _create_user(db, "bob", "bob@example.com")
        _add_bookmarks(db, alice, ALICE_BOOKMARKS)
        _add_bookmarks(db, bob, BOB_BOOKMARKS)

        print("Seeded sample data:")
        print(f"  alice@example.com / {SEED_PASSWORD}  ({len(ALICE_BOOKMARKS)} bookmarks)")
        print(f"  bob@example.com   / {SEED_PASSWORD}  ({len(BOB_BOOKMARKS)} bookmarks)")
        print(f"  tags: {db.query(Tag).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
