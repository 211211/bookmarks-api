"""Authentication request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

# A small denylist of the most common passwords. Not a substitute for a full
# breached-password (k-anonymity / HIBP) check, but blocks the obvious ones.
_COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "12345678",
    "123456789",
    "qwertyuiop",
    "qwerty123",
    "letmein1",
    "iloveyou",
    "admin123",
    "welcome1",
    "changeme",
}


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
        min_length=10,
        max_length=128,
        description="At least 10 characters; not a common password and not similar "
        "to your username or email.",
        examples=["s3cret-passw0rd!"],
    )

    @model_validator(mode="after")
    def _password_strength(self) -> RegisterRequest:
        pw = self.password
        low = pw.lower()
        if low in _COMMON_PASSWORDS:
            raise ValueError("This password is too common; choose a less guessable one.")
        # Reject passwords that embed the username or the email local-part.
        username = (self.username or "").lower()
        local = (self.email or "").split("@", 1)[0].lower()
        for token in (username, local):
            if len(token) >= 3 and token in low:
                raise ValueError("Password must not contain your username or email.")
        return self


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
