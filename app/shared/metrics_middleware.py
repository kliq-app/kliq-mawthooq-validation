from __future__ import annotations

import time

from app.shared.metrics import metrics


class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        start = time.monotonic()
        status_code_holder = {"value": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_holder["value"] = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            metrics.observe_request(method, path, status_code_holder["value"], duration)
