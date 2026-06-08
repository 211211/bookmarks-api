"""Bookmark request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.schemas.common import PageMeta
from app.schemas.tag import normalize_tags


class BookmarkCreate(BaseModel):
    url: HttpUrl = Field(..., examples=["https://example.com/article"])
    title: str = Field(..., min_length=1, max_length=200, examples=["Great Article"])
    description: str | None = Field(
        default=None, max_length=500, examples=["An insightful read on backend design."]
    )
    tags: list[str] = Field(default_factory=list, examples=[["python", "tutorial", "backend"]])

    @field_validator("tags")
    @classmethod
    def _normalize(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class BookmarkUpdate(BaseModel):
    """Partial update — only the fields present in the request body are applied."""

    url: HttpUrl | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def _normalize(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_tags(value)


class BookmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    description: str | None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    version: int = Field(
        ...,
        description="Optimistic-concurrency version; also returned as the ETag header.",
        examples=[1],
    )

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_names(cls, value: object) -> list[str]:
        """Accept either a list of ORM `Tag` objects or plain strings."""
        if value is None:
            return []
        return [t if isinstance(t, str) else t.name for t in value]  # type: ignore[union-attr]


class BookmarkPage(BaseModel):
    items: list[BookmarkOut]
    pagination: PageMeta
