import asyncio
import sys


def ensure_windows_selector_event_loop() -> None:
    """psycopg3's async mode cannot run on Windows' default ProactorEventLoop.

    Must be called before any asyncio event loop is created (e.g. before
    ``asyncio.run()`` or before a Uvicorn/ASGI server starts its loop).
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
