"""Service-layer unit tests.

These exercise the services against in-memory fakes that implement the repository
and utility *interfaces* — no database, no bcrypt, no HTTP. This is the payoff of
the repository pattern: business logic is testable in isolation.
"""

import pytest

from app.core.errors import (
    AuthError,
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
)
from app.models import Bookmark, Tag, User
from app.repositories.bookmark.interface import BookmarkFilters, IBookmarkRepository
from app.repositories.tag.interface import ITagRepository
from app.repositories.user.interface import IUserRepository
from app.services.auth.service import AuthService
from app.services.bookmark.service import BookmarkService
from app.utils.etag.etag import VersionETagService
from app.utils.security.interface import IPasswordHasher, ITokenProvider
from app.utils.tags.normalizer import TagNormalizer


# ── Fakes ───────────────────────────────────────────────────────────────────
class FakeUserRepository(IUserRepository):
    def __init__(self):
        self.users: dict[int, User] = {}
        self._seq = 0

    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def get_by_email(self, email):
        return next((u for u in self.users.values() if u.email == email.strip().lower()), None)

    def get_by_username(self, username):
        return next((u for u in self.users.values() if u.username == username), None)

    def add(self, user):
        self._seq += 1
        user.id = self._seq
        self.users[user.id] = user
        return user


class FakeTagRepository(ITagRepository):
    def __init__(self):
        self._by_name: dict[str, Tag] = {}
        self._seq = 0

    def get_or_create(self, names):
        out = []
        for name in names:
            tag = self._by_name.get(name)
            if tag is None:
                self._seq += 1
                tag = Tag(id=self._seq, name=name)
                self._by_name[name] = tag
            out.append(tag)
        return out


class FakeBookmarkRepository(IBookmarkRepository):
    def __init__(self):
        self.items: dict[int, Bookmark] = {}
        self._seq = 0

    def add(self, bookmark):
        self._seq += 1
        bookmark.id = self._seq
        if bookmark.version is None:
            bookmark.version = 1
        self.items[bookmark.id] = bookmark
        return bookmark

    def get_owned(self, user_id, bookmark_id):
        bm = self.items.get(bookmark_id)
        return bm if bm and bm.user_id == user_id else None

    def update(self, bookmark):
        bookmark.version += 1  # mimic version_id_col bump on a real UPDATE
        return bookmark

    def delete(self, bookmark):
        self.items.pop(bookmark.id, None)

    def _owned(self, user_id, filters: BookmarkFilters):
        rows = [b for b in self.items.values() if b.user_id == user_id]
        if filters.tag:
            rows = [b for b in rows if any(t.name == filters.tag for t in b.tags)]
        return sorted(rows, key=lambda b: b.id, reverse=True)

    def count(self, user_id, filters):
        return len(self._owned(user_id, filters))

    def list_offset(self, user_id, filters, *, sort, limit, offset):
        return self._owned(user_id, filters)[offset : offset + limit]

    def list_keyset(self, user_id, filters, *, cursor, limit):
        return [b for b in self._owned(user_id, filters) if b.id < cursor][:limit]


class FakePasswordHasher(IPasswordHasher):
    def hash(self, password):
        return f"hashed::{password}"

    def verify(self, password, password_hash):
        return password_hash == f"hashed::{password}"


class FakeTokenProvider(ITokenProvider):
    def create_access_token(self, subject, expires_minutes=None):
        return f"token-for-{subject}"

    def decode(self, token):
        return {"sub": token.removeprefix("token-for-")}


# ── AuthService ─────────────────────────────────────────────────────────────
def _auth_service():
    return AuthService(FakeUserRepository(), FakePasswordHasher(), FakeTokenProvider())


def test_register_returns_user_and_token():
    svc = _auth_service()
    user, token = svc.register(username="alice", email="Alice@Example.com", password="pw12345678")
    assert user.id == 1
    assert user.email == "alice@example.com"  # normalized
    assert user.password_hash == "hashed::pw12345678"  # hashed, not plaintext
    assert token == "token-for-1"


def test_register_duplicate_email_conflicts():
    svc = _auth_service()
    svc.register(username="alice", email="a@example.com", password="pw12345678")
    with pytest.raises(ConflictError):
        svc.register(username="alice2", email="a@example.com", password="pw12345678")


def test_login_success_and_failures():
    svc = _auth_service()
    svc.register(username="alice", email="a@example.com", password="secret123")

    user, token = svc.login(email="a@example.com", password="secret123")
    assert token == f"token-for-{user.id}"

    with pytest.raises(AuthError):
        svc.login(email="a@example.com", password="wrong")
    with pytest.raises(AuthError):
        svc.login(email="nobody@example.com", password="whatever")


# ── BookmarkService ─────────────────────────────────────────────────────────
def _bookmark_service():
    return BookmarkService(
        FakeBookmarkRepository(), FakeTagRepository(), TagNormalizer(), VersionETagService()
    )


def test_create_normalizes_tags_and_scopes_owner():
    svc = _bookmark_service()
    bm = svc.create(
        user_id=7, url="https://x.com", title="X", description=None, tags=["Py", "py", "  SQL "]
    )
    assert bm.id == 1
    assert bm.user_id == 7
    assert sorted(t.name for t in bm.tags) == ["py", "sql"]


def test_get_missing_raises_not_found():
    svc = _bookmark_service()
    with pytest.raises(NotFoundError):
        svc.get(user_id=1, bookmark_id=999)


def test_get_is_owner_scoped():
    svc = _bookmark_service()
    bm = svc.create(user_id=1, url="https://x.com", title="X", description=None, tags=[])
    # A different user cannot fetch it.
    with pytest.raises(NotFoundError):
        svc.get(user_id=2, bookmark_id=bm.id)
    assert svc.get(user_id=1, bookmark_id=bm.id).id == bm.id


def test_list_pagination_metadata():
    svc = _bookmark_service()
    for i in range(5):
        svc.create(user_id=1, url=f"https://x{i}.com", title=f"T{i}", description=None, tags=[])

    page1 = svc.list(user_id=1, page=1, per_page=2)
    assert len(page1["items"]) == 2
    assert page1["total"] == 5
    assert page1["total_pages"] == 3
    assert page1["has_next"] is True and page1["has_prev"] is False


# ── Optimistic concurrency (If-Match) ────────────────────────────────────────
def test_update_requires_if_match():
    svc = _bookmark_service()
    bm = svc.create(user_id=1, url="https://x.com", title="X", description=None, tags=[])
    with pytest.raises(PreconditionRequiredError):
        svc.update(user_id=1, bookmark_id=bm.id, changes={"title": "Y"}, if_match=None)


def test_update_stale_if_match_conflicts():
    svc = _bookmark_service()
    bm = svc.create(user_id=1, url="https://x.com", title="X", description=None, tags=[])
    with pytest.raises(PreconditionFailedError):
        svc.update(user_id=1, bookmark_id=bm.id, changes={"title": "Y"}, if_match='"999"')


def test_update_with_correct_if_match_bumps_version():
    svc = _bookmark_service()
    bm = svc.create(user_id=1, url="https://x.com", title="X", description=None, tags=[])
    assert bm.version == 1
    updated = svc.update(user_id=1, bookmark_id=bm.id, changes={"title": "Y"}, if_match='"1"')
    assert updated.version == 2

    # The old ETag is now stale → second update with it conflicts (lost-update guard).
    with pytest.raises(PreconditionFailedError):
        svc.update(user_id=1, bookmark_id=bm.id, changes={"title": "Z"}, if_match='"1"')


def test_delete_requires_and_validates_if_match():
    svc = _bookmark_service()
    bm = svc.create(user_id=1, url="https://x.com", title="X", description=None, tags=[])
    with pytest.raises(PreconditionRequiredError):
        svc.delete(user_id=1, bookmark_id=bm.id, if_match=None)
    with pytest.raises(PreconditionFailedError):
        svc.delete(user_id=1, bookmark_id=bm.id, if_match='"999"')
    svc.delete(user_id=1, bookmark_id=bm.id, if_match='"1"')  # correct → succeeds
