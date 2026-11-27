"""Keeps a free-tier host awake while an experiment is running.

Free hosting plans (e.g. Render Free) put the app to sleep after a period
without inbound requests, which would kill a run if nobody keeps the page open.
While at least one run is active, this loop requests the app's own public URL
every few minutes so the host keeps seeing traffic. When no run is active it
does nothing, so the app can still sleep normally.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 5 * 60


def is_public_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return url.startswith(("http://", "https://")) and host not in {"localhost", "127.0.0.1", "0.0.0.0", ""}


async def keep_alive_loop(public_url: str, has_active_runs: Callable[[], bool]) -> None:
    target = public_url.rstrip("/") + "/healthz"
    while True:
        await asyncio.sleep(PING_INTERVAL_SECONDS)
        if not has_active_runs():
            continue
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                await http.get(target)
        except httpx.HTTPError as exc:
            logger.info("Keep-alive ping failed: %s", type(exc).__name__)
