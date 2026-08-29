"""Records http_requests_total / http_request_duration_seconds for every request.

Plain ASGI middleware, not Starlette's BaseHTTPMiddleware — the latter
buffers in a way that interferes with StreamingResponse, which the SSE
execution-stream endpoint depends on.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.metrics import http_request_duration_seconds, http_requests_total

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class MetricsMiddleware:
    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        start = time.monotonic()
        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        # scope["route"] is the path template, not the resolved path with a
        # real id — avoids unbounded label cardinality.
        route = scope.get("route")
        path = route.path if route is not None else scope["path"]
        status = status_holder.get("status", 500)

        http_requests_total.labels(method=method, path=path, status=str(status)).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(
            time.monotonic() - start
        )
