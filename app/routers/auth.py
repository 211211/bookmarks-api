"""Authentication routes: registration and login (JWT issuance)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.config import get_settings
from app.core.deps import get_auth_service
from app.core.rate_limit import limiter
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.schemas.common import ErrorResponse
from app.services.auth.interface import IAuthService

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])


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
    service: IAuthService = Depends(get_auth_service),
) -> AuthResponse:
    user, token = service.register(
        username=payload.username, email=payload.email, password=payload.password
    )
    return AuthResponse(user=UserOut.model_validate(user), token=token)


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
    service: IAuthService = Depends(get_auth_service),
) -> AuthResponse:
    user, token = service.login(email=payload.email, password=payload.password)
    return AuthResponse(user=UserOut.model_validate(user), token=token)
