"""Application configuration loaded from environment variables / `.env`."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known placeholder secrets that must never be used outside local development.
_PLACEHOLDER_SECRETS = {
    "",
    "secret",
    "change-me",
    "dev-secret-change-me-to-a-long-random-string-please",
    "change-me-to-a-long-random-string-in-production",
}
_DEV_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are read from environment variables (case-insensitive) and an
    optional `.env` file. Sensible defaults keep local development zero-config.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Bookmarks API"
    environment: str = "development"

    # Database — SQLite by default; switch to PostgreSQL via DATABASE_URL.
    database_url: str = "sqlite:///./bookmarks.db"

    # JWT
    jwt_secret: str = "dev-secret-change-me-to-a-long-random-string-please"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24  # 24 hours

    # Rate limiting (bonus)
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_auth: str = "15/minute"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @model_validator(mode="after")
    def _enforce_strong_secret(self) -> "Settings":
        """Fail closed: outside development, refuse to start with a weak, empty,
        or well-known default JWT secret (which would allow token forgery)."""
        if self.environment.lower() not in _DEV_ENVIRONMENTS:
            if self.jwt_secret in _PLACEHOLDER_SECRETS or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be a strong, unique value of at least 32 characters "
                    "outside development. Generate one with: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance (read once per process)."""
    return Settings()
