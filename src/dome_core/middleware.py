from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, environment: str = "production") -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._environment = environment

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if self._environment in ("staging", "production"):
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
