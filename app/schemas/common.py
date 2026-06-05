"""Shared response schemas: pagination envelope and the error envelope."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PageMeta(BaseModel):
    """Pagination metadata returned alongside a page of results."""

    page: int = Field(..., examples=[1])
    per_page: int = Field(..., examples=[20])
    total: int = Field(..., description="Total matching records.", examples=[142])
    total_pages: int = Field(..., examples=[8])
    has_next: bool
    has_prev: bool
    next_cursor: int | None = Field(
        default=None,
        description="Opaque keyset cursor for the next page (bonus cursor pagination).",
        examples=[123],
    )


class ErrorBody(BaseModel):
    code: str = Field(..., examples=["VALIDATION_ERROR"])
    message: str = Field(..., examples=["Title is required and must be under 200 characters."])
    details: dict[str, Any] | None = Field(
        default=None,
        examples=[{"field": "title", "constraint": "max_length", "limit": 200}],
    )


class ErrorResponse(BaseModel):
    """The single, consistent shape of every non-2xx response."""

    error: ErrorBody
