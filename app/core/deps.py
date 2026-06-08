"""Dependency-injection wiring.

Composes the object graph for each request: stateless utilities are shared
singletons; repositories are bound to the request's DB session; services receive
repository/utility *interfaces*. Routes depend only on the service interfaces and
on ``get_current_user``.
"""

from __future__ import annotations

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AuthError
from app.database import get_db
from app.models import User
from app.repositories.bookmark.interface import IBookmarkRepository
from app.repositories.bookmark.repository import BookmarkRepository
from app.repositories.stats.interface import IStatsRepository
from app.repositories.stats.repository import StatsRepository
from app.repositories.tag.interface import ITagRepository
from app.repositories.tag.repository import TagRepository
from app.repositories.user.interface import IUserRepository
from app.repositories.user.repository import UserRepository
from app.services.auth.interface import IAuthService
from app.services.auth.service import AuthService
from app.services.bookmark.interface import IBookmarkService
from app.services.bookmark.service import BookmarkService
from app.services.stats.interface import IStatsService
from app.services.stats.service import StatsService
from app.utils.etag.etag import VersionETagService
from app.utils.etag.interface import IETagService
from app.utils.security.interface import IPasswordHasher, ITokenProvider
from app.utils.security.password import BcryptPasswordHasher
from app.utils.security.token import JwtTokenProvider
from app.utils.tags.interface import ITagNormalizer
from app.utils.tags.normalizer import TagNormalizer

_settings = get_settings()

# ── Stateless utility singletons ───────────────────────────────────────────
_password_hasher: IPasswordHasher = BcryptPasswordHasher()
_token_provider: ITokenProvider = JwtTokenProvider(
    secret=_settings.jwt_secret,
    algorithm=_settings.jwt_algorithm,
    expires_minutes=_settings.jwt_expires_minutes,
)
_tag_normalizer: ITagNormalizer = TagNormalizer()
_etag_service: IETagService = VersionETagService()


def get_password_hasher() -> IPasswordHasher:
    return _password_hasher


def get_token_provider() -> ITokenProvider:
    return _token_provider


def get_tag_normalizer() -> ITagNormalizer:
    return _tag_normalizer


def get_etag_service() -> IETagService:
    return _etag_service


# ── Repositories (per request, bound to the session) ───────────────────────
def get_user_repository(db: Session = Depends(get_db)) -> IUserRepository:
    return UserRepository(db)


def get_bookmark_repository(db: Session = Depends(get_db)) -> IBookmarkRepository:
    return BookmarkRepository(db)


def get_tag_repository(db: Session = Depends(get_db)) -> ITagRepository:
    return TagRepository(db)


def get_stats_repository(db: Session = Depends(get_db)) -> IStatsRepository:
    return StatsRepository(db)


# ── Services ───────────────────────────────────────────────────────────────
def get_auth_service(
    users: IUserRepository = Depends(get_user_repository),
    hasher: IPasswordHasher = Depends(get_password_hasher),
    tokens: ITokenProvider = Depends(get_token_provider),
) -> IAuthService:
    return AuthService(users, hasher, tokens)


def get_bookmark_service(
    bookmarks: IBookmarkRepository = Depends(get_bookmark_repository),
    tags: ITagRepository = Depends(get_tag_repository),
    normalizer: ITagNormalizer = Depends(get_tag_normalizer),
    etags: IETagService = Depends(get_etag_service),
) -> IBookmarkService:
    return BookmarkService(bookmarks, tags, normalizer, etags)


def get_stats_service(
    stats: IStatsRepository = Depends(get_stats_repository),
) -> IStatsService:
    return StatsService(stats)


# ── Authenticated user ─────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    tokens: ITokenProvider = Depends(get_token_provider),
    users: IUserRepository = Depends(get_user_repository),
) -> User:
    """Resolve the authenticated user from a bearer JWT, or raise ``AuthError``."""
    if credentials is None or not credentials.credentials:
        raise AuthError("Authentication credentials were not provided.")

    try:
        payload = tokens.decode(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid authentication token.") from exc

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise AuthError("Invalid authentication token.") from exc

    user = users.get_by_id(user_id)
    if user is None:
        raise AuthError("User account no longer exists.")
    return user
