"""Cached list of OpenRouter model ids, used for suggestions and pre-run validation."""

from __future__ import annotations

import logging
import time

from backend.openrouter.client import OpenRouterClient

logger = logging.getLogger(__name__)

CACHE_SECONDS = 3600


class ModelCatalog:
    def __init__(self, client: OpenRouterClient):
        self._client = client
        self._models: list[str] = []
        self._fetched_at = 0.0

    async def get_models(self) -> list[str]:
        """Return known model ids, or [] if the list cannot be fetched."""
        if self._models and time.monotonic() - self._fetched_at < CACHE_SECONDS:
            return self._models
        try:
            self._models = await self._client.list_models()
            self._fetched_at = time.monotonic()
        except Exception as exc:  # validation is best-effort
            logger.warning("Could not fetch OpenRouter model list: %s", type(exc).__name__)
        return self._models

    async def find_unknown(self, model_ids: list[str]) -> list[str]:
        """Return ids not found on OpenRouter. Empty if the catalog is unavailable."""
        known = set(await self.get_models())
        if not known:
            return []
        return sorted({m for m in model_ids if m not in known and not m.startswith("~")})
