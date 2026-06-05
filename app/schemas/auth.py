"""Authentication request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=80,
        pattern=r"^[A-Za-z0-9_.-]+$",
        description="3–80 chars; letters, digits, '_', '.', '-'.",
        examples=["alice"],
    )
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="At least 8 characters.",
        examples=["s3cret-passw0rd"],
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(..., min_length=1, examples=["s3cret-passw0rd"])


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    token: str = Field(..., description="Signed JWT access token.")
    token_type: str = Field(default="bearer")
