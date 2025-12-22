from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from app.shared.errors import ErrorDetail, ErrorResponse
from app.shared.rate_limiter import rate_limiter
from app.shared.settings import settings


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        api_keys = settings.api_keys
        api_key = request.headers.get("x-api-key")
        path = scope.get("path", "")
        requires_api_key = path.startswith("/v1")

        if api_keys and requires_api_key:
            if not api_key or api_key not in api_keys:
                response = _error_response(401, "unauthorized", "API key required")
                await response(scope, receive, send)
                return

        ip_address = _resolve_ip(request)
        limit = settings.rate_limit_per_min
        window_sec = 60

        if not await rate_limiter.allow(f"ip:{ip_address}", limit, window_sec):
            response = _error_response(429, "rate_limited", "Rate limit exceeded")
            await response(scope, receive, send)
            return

        if api_keys and api_key:
            if not await rate_limiter.allow(f"key:{api_key}", limit, window_sec):
                response = _error_response(429, "rate_limited", "Rate limit exceeded")
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def _resolve_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump())
