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
    # This API only ever serves JSON — nosniff stops a browser from
    # second-guessing that and executing a response as script/HTML.
    (b"x-content-type-options", b"nosniff"),
    # No response from this API is meant to be framed by another site.
    (b"x-frame-options", b"DENY"),
    # Don't leak the full request URL (which can contain resource ids) to
    # third-party origins a client might navigate to afterward.
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    # This is a JSON API with no use for any browser feature here — deny
    # them all rather than enumerate an allowlist that will drift.
    (b"permissions-policy", b"geolocation=(), camera=(), microphone=()"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app
        # HSTS only makes sense once the app is actually served over HTTPS —
        # asserting it in local HTTP dev would be a lie the browser ignores
        # anyway, but there's no reason to emit a header that's meaningless
        # for the environment it's answering in.
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
