"""HTTP middleware: correlation ids, access logs and security headers."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, request_id_var, user_var

logger = get_logger("app.access")

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cache-Control": "no-store",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if incoming and len(incoming) <= 128 else uuid.uuid4().hex
        request.state.request_id = request_id
        request.state.started_at = time.perf_counter()
        token = request_id_var.set(request_id)
        user_token = user_var.set("-")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - request.state.started_at) * 1000
            logger.exception(
                "unhandled request error",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "request_id": request_id,
                },
            )
            raise
        finally:
            # Reset after logging so the access entry keeps its correlation id.
            request_id_var.reset(token)
            user_var.reset(user_token)

        duration_ms = (time.perf_counter() - request.state.started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if not request.url.path.startswith(_DOC_PATHS):
            response.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )

        logger.info(
            "http request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "client_ip": get_client_ip(request),
                "request_id": request_id,
                "user": getattr(request.state, "user_email", "-"),
            },
        )
        return response


def get_client_ip(request: Request) -> str:
    """Resolve the caller address, honouring a single trusted proxy hop."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
