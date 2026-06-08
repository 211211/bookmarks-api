"""Genuine DB-level optimistic-concurrency races.

Uses two independent sessions on a file-backed SQLite database so each has its
own connection and transaction (unlike the shared in-memory test engine). This
exercises the real ``version_id_col`` backstop and the
``StaleDataError -> StaleVersionError`` translation in the repository — the part
the app-level ``If-Match`` fast-path cannot prove on its own.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (register models on Base.metadata)
from app.database import Base
from app.models import Bookmark, User
from app.repositories.bookmark.interface import StaleVersionError
from app.repositories.bookmark.repository import BookmarkRepository
from app.repositories.tag.repository import TagRepository


@pytest.fixture
def db_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    s0 = Session()
    user = User(username="c", email="c@e.com", password_hash="x")
    s0.add(user)
    s0.commit()
    bm = Bookmark(url="https://x.com", title="orig", user_id=user.id)
    s0.add(bm)
    s0.commit()
    uid, bid = user.id, bm.id
    s0.close()

    yield Session, uid, bid
    engine.dispose()


def test_tag_only_update_bumps_version(db_factory):
    """Regression: a tag-only edit must advance the version (otherwise the ETag
    freezes and the lost-update guard is defeated for tag changes)."""
    Session, uid, bid = db_factory
    s = Session()
    repo = BookmarkRepository(s)
    bm = repo.get_owned(uid, bid)
    assert bm.version == 1
    bm.tags = TagRepository(s).get_or_create(["alpha"])
    repo.update(bm)
    assert bm.version == 2
    s.close()


def test_scalar_vs_tag_only_race_is_detected(db_factory):
    """Two writers both load v1 and both pass an If-Match='1' check; the first
    (scalar) commit wins, the second (tag-only) must lose the race -> conflict."""
    Session, uid, bid = db_factory
    sA, sB = Session(), Session()
    rA, rB = BookmarkRepository(sA), BookmarkRepository(sB)
    bA, bB = rA.get_owned(uid, bid), rB.get_owned(uid, bid)
    assert bA.version == bB.version == 1

    bA.title = "from A"
    rA.update(bA)  # commits -> version 2

    bB.tags = TagRepository(sB).get_or_create(["beta"])
    with pytest.raises(StaleVersionError):
        rB.update(bB)
    sA.close()
    sB.close()


def test_tag_only_vs_tag_only_race_is_detected(db_factory):
    """Two concurrent tag-only edits must not both succeed (no silent lost
    update, and a duplicate association collision surfaces as a conflict, not 500)."""
    Session, uid, bid = db_factory
    sA, sB = Session(), Session()
    rA, rB = BookmarkRepository(sA), BookmarkRepository(sB)
    bA, bB = rA.get_owned(uid, bid), rB.get_owned(uid, bid)

    bA.tags = TagRepository(sA).get_or_create(["alpha"])
    rA.update(bA)  # version -> 2

    bB.tags = TagRepository(sB).get_or_create(["beta"])
    with pytest.raises(StaleVersionError):
        rB.update(bB)
    sA.close()
    sB.close()


def test_delete_vs_update_race_is_detected(db_factory):
    """An update that loaded v1 must fail if the row was deleted concurrently."""
    Session, uid, bid = db_factory
    sA, sB = Session(), Session()
    rA, rB = BookmarkRepository(sA), BookmarkRepository(sB)
    bA, bB = rA.get_owned(uid, bid), rB.get_owned(uid, bid)

    rA.delete(bA)  # row gone

    bB.title = "too late"
    with pytest.raises(StaleVersionError):
        rB.update(bB)
    sA.close()
    sB.close()
