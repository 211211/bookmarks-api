"""Typed application errors and global exception handlers.

Every error response — whether raised by our code, by FastAPI request
validation, by an `HTTPException`, or by an unexpected crash — is rendered in a
single consistent JSON envelope::

    { "error": { "code": ..., "message": ..., "details": {...} } }
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("bookmarks.errors")


class AppError(Exception):
    """Base class for expected, mapped application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class AuthError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_ERROR"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


class PreconditionRequiredError(AppError):
    """The request must be made conditional (missing `If-Match`)."""

    status_code = status.HTTP_428_PRECONDITION_REQUIRED
    code = "PRECONDITION_REQUIRED"


class PreconditionFailedError(AppError):
    """The supplied `If-Match` did not match the current resource version
    (optimistic-concurrency conflict — the resource changed under the client)."""

    status_code = status.HTTP_412_PRECONDITION_FAILED
    code = "PRECONDITION_FAILED"


class TooManyAttemptsError(AppError):
    """Account temporarily locked after too many failed login attempts."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "TOO_MANY_ATTEMPTS"


# Maps HTTP status codes to stable, machine-readable error codes.
_STATUS_TO_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_ERROR",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    412: "PRECONDITION_FAILED",
    422: "VALIDATION_ERROR",
    428: "PRECONDITION_REQUIRED",
    429: "RATE_LIMITED",
}


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def _field_path(loc: tuple[Any, ...]) -> str:
    """Render a Pydantic error location as a dotted field path, dropping the
    leading ``body``/``query``/``path`` segment."""
    parts = [str(p) for p in loc if p not in ("body",)]
    return ".".join(parts) if parts else "(root)"


def _humanize_validation(errors: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Turn Pydantic's error list into a human message plus structured details."""
    first = errors[0]
    field = _field_path(tuple(first.get("loc", ())))
    constraint = str(first.get("type", "invalid"))
    message = f"{field}: {first.get('msg', 'Invalid value.')}"

    details: dict[str, Any] = {"field": field, "constraint": constraint}
    ctx = first.get("ctx") or {}
    for key in ("limit_value", "max_length", "min_length", "ge", "le", "gt", "lt"):
        if key in ctx:
            details["limit"] = ctx[key]
            break

    if len(errors) > 1:
        details["fields"] = [
            {"field": _field_path(tuple(e.get("loc", ()))), "message": e.get("msg", "")}
            for e in errors
        ]
    return message, details


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI app."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        message, details = _humanize_validation(exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("VALIDATION_ERROR", message, details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed."
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, message),
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
