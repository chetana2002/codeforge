"""Records http_requests_total / http_request_duration_seconds for every request.

Implemented as a plain ASGI middleware rather than Starlette's
BaseHTTPMiddleware: BaseHTTPMiddleware buffers through an internal memory
stream that has known interactions with StreamingResponse (delayed
first-byte flushing, and interference with a request's own disconnect
detection) — exactly the two things the SSE execution-stream endpoint
depends on. Wrapping `send` here instead passes every message straight
through unmodified; the middleware only peeks at the status code on
http.response.start, so it can't affect timing or streaming behavior.
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

        # Set once routing has resolved (i.e. after self.app returns) so this is the
        # route's path *template* ("/executions/{execution_id}"), not the resolved
        # path with a real id in it — using the resolved path would give every
        # distinct execution/project/file its own metric series and grow unbounded.
        route = scope.get("route")
        path = route.path if route is not None else scope["path"]
        status = status_holder.get("status", 500)

        http_requests_total.labels(method=method, path=path, status=str(status)).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(
            time.monotonic() - start
        )
