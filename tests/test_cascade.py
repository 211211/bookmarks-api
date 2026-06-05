"""Foreign-key ON DELETE CASCADE behaviour (depends on the SQLite FK pragma)."""

from sqlalchemy import func, select

from app.models import Bookmark, User
from app.models.associations import bookmark_tags
from tests.conftest import TestingSessionLocal, auth_header, register


def test_deleting_user_cascades_to_bookmarks_and_links(client):
    data = register(client)
    headers = auth_header(data["token"])
    user_id = data["user"]["id"]

    client.post(
        "/api/bookmarks",
        json={"url": "https://a.com", "title": "A", "tags": ["x", "y"]},
        headers=headers,
    )
    client.post(
        "/api/bookmarks",
        json={"url": "https://b.com", "title": "B", "tags": ["y", "z"]},
        headers=headers,
    )

    db = TestingSessionLocal()
    try:
        assert db.scalar(
            select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user_id)
        ) == 2
        assert db.scalar(select(func.count()).select_from(bookmark_tags)) == 4

        # Deleting the user must cascade to their bookmarks and the m2m links.
        db.delete(db.get(User, user_id))
        db.commit()

        assert db.scalar(
            select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user_id)
        ) == 0
        assert db.scalar(select(func.count()).select_from(bookmark_tags)) == 0
    finally:
        db.close()
