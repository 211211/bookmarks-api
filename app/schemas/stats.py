"""Statistics response schemas (raw-SQL aggregation endpoint)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TagCount(BaseModel):
    name: str = Field(..., examples=["python"])
    count: int = Field(..., examples=[45])


class MonthCount(BaseModel):
    month: str = Field(..., description="YYYY-MM bucket.", examples=["2025-01"])
    count: int = Field(..., examples=[23])


class StatsResponse(BaseModel):
    total_bookmarks: int = Field(..., examples=[142])
    total_tags: int = Field(..., examples=[28])
    top_tags: list[TagCount]
    bookmarks_per_month: list[MonthCount]
