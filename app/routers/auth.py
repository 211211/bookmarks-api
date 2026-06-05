"""Authentication routes: registration and login (JWT issuance)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.crud import users
from app.database import get_db
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.schemas.common import ErrorResponse

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_response(user) -> AuthResponse:
    token = create_access_token(user.id)
    return AuthResponse(user=UserOut.model_validate(user), token=token)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        409: {"model": ErrorResponse, "description": "Email or username already in use."},
        422: {"model": ErrorResponse, "description": "Validation error."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
@limiter.limit(settings.rate_limit_auth)
def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = users.create_user(
        db, username=payload.username, email=payload.email, password=payload.password
    )
    return _auth_response(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate and receive a JWT",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials."},
        422: {"model": ErrorResponse, "description": "Validation error."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
@limiter.limit(settings.rate_limit_auth)
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = users.authenticate(db, email=payload.email, password=payload.password)
    return _auth_response(user)
