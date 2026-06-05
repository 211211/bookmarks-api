"""Application configuration loaded from environment variables / `.env`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance (read once per process)."""
    return Settings()
