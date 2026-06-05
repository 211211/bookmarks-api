"""bcrypt-based password hasher."""

from __future__ import annotations

import bcrypt as _bcrypt

# Compatibility shim: passlib 1.7.4 probes ``bcrypt.__about__.__version__``,
# which bcrypt >= 4.1 removed. Provide it so the backend loads without a noisy
# (harmless) traceback on first use.
if not hasattr(_bcrypt, "__about__"):  # pragma: no cover - environment shim

    class _About:
        __version__ = getattr(_bcrypt, "__version__", "4.1.0")

    _bcrypt.__about__ = _About  # type: ignore[attr-defined]

from passlib.context import CryptContext  # noqa: E402

from app.utils.security.interface import IPasswordHasher  # noqa: E402


class BcryptPasswordHasher(IPasswordHasher):
    """Hashes passwords with ``bcrypt_sha256`` (HMAC-pre-hashes the input so the
    full password is used — plain bcrypt silently ignores bytes past 72)."""

    def __init__(self) -> None:
        self._context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

    def hash(self, password: str) -> str:
        return self._context.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._context.verify(password, password_hash)
