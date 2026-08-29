"""Sets standard defensive HTTP response headers on every API response.

Plain ASGI middleware (same reasoning as MetricsMiddleware): it only appends
headers to the outgoing http.response.start message, so it can't affect
streaming timing or the SSE endpoint's own disconnect handling.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import get_settings

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

_STATIC_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"geolocation=(), camera=(), microphone=()"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app
        # HSTS only makes sense once actually served over HTTPS.
        self._is_production = get_settings().is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_STATIC_HEADERS)
                if self._is_production:
                    headers.append(
                        (b"strict-transport-security", b"max-age=63072000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
