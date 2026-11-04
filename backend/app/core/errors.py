"""Domain error hierarchy and FastAPI exception handlers.

Every error leaves the API as a stable, machine readable envelope:

    {"error": {"code": "...", "message": "...", "request_id": "...", "details": {...}}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_var

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all expected application failures."""

    code: str = "internal_error"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)


class ValidationError(AppError):
    code = "validation_error"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "The request payload is invalid."


class AuthenticationError(AppError):
    code = "authentication_failed"
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Invalid or expired credentials."


class PermissionDenied(AppError):
    code = "permission_denied"
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT
    default_message = "The request conflicts with the current state."


class RateLimited(AppError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_message = "Too many requests. Try again later."


class ProviderUnavailable(AppError):
    code = "provider_unavailable"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "The cloud provider is currently unavailable."


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id_var.get(),
            "details": details or {},
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("application error", extra={"error_code": exc.code, "detail": exc.message})
        else:
            logger.info(
                "request rejected",
                extra={"error_code": exc.code, "detail": exc.message, "status": exc.status_code},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = {
            "fields": [
                {
                    "location": ".".join(str(part) for part in error.get("loc", [])),
                    "message": error.get("msg", ""),
                    "type": error.get("type", ""),
                }
                for error in exc.errors()
            ]
        }
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("validation_error", "The request payload is invalid.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "authentication_failed",
            403: "permission_denied",
            404: "not_found",
            405: "method_not_allowed",
            409: "conflict",
            429: "rate_limited",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail)),
            headers=getattr(exc, "headers", None) or {},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception", extra={"error_type": type(exc).__name__})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred."),
        )
