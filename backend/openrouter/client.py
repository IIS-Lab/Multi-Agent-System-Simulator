"""Minimal async OpenRouter client (server-side only).

The API key is held only in this object. It is never logged, returned to the
browser, or written into results.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from backend.config.simulation_defaults import RATE_LIMIT_BACKOFF_SECONDS

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """A failed model request. `kind` is a stable identifier stored in results."""

    def __init__(self, kind: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retryable = retryable


@dataclass
class Completion:
    content: str
    model: str
    provider: str | None = None
    generation_id: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    cost: float | None = None
    latency_ms: int = 0
    attempts: int = 1


class LLMClient(Protocol):
    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float,
        reasoning_effort: str | None = None,
        json_output: bool = False,
    ) -> Completion: ...


class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str, app_url: str, app_title: str = "MASS - Multi Agent System Simulator"):
        self._api_key = api_key
        self._base_url = base_url
        self._headers = {
            "HTTP-Referer": app_url,
            "X-Title": app_title,
            "Content-Type": "application/json",
        }

    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float,
        reasoning_effort: str | None = None,
        json_output: bool = False,
    ) -> Completion:
        if not self._api_key:
            raise LLMError("configuration", "OPENROUTER_API_KEY is not set on the server.")

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        # OpenRouter ignores parameters a model does not support.
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort, "exclude": True}
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        headers = {**self._headers, "Authorization": f"Bearer {self._api_key}"}
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                response = await http.post(f"{self._base_url}/chat/completions", json=payload, headers=headers)
        except httpx.TimeoutException:
            raise LLMError("timeout", f"The request to model '{model}' timed out.", retryable=True)
        except httpx.HTTPError as exc:
            raise LLMError("network", f"Network error while calling OpenRouter ({type(exc).__name__}).", retryable=True)
        latency_ms = int((time.monotonic() - started) * 1000)

        data = _safe_json(response)
        if response.status_code != 200 or "error" in data:
            raise _error_from_response(response.status_code, data, model)

        choices = data.get("choices") or []
        if not choices:
            raise LLMError("empty_response", f"Model '{model}' returned no choices.", retryable=True)
        choice = choices[0]
        content = ((choice.get("message") or {}).get("content") or "").strip()
        if not content:
            if choice.get("finish_reason") == "length":
                raise LLMError(
                    "max_tokens",
                    f"Model '{model}' used up max_tokens (often on hidden reasoning) before writing a reply. "
                    "Increase MAX_TOKENS or lower REASONING_EFFORT in backend/config/simulation_defaults.py.",
                )
            raise LLMError("empty_response", f"Model '{model}' returned an empty message.", retryable=True)

        usage = data.get("usage") or {}
        reasoning_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        return Completion(
            content=content,
            model=data.get("model") or model,
            provider=data.get("provider"),
            generation_id=data.get("id"),
            finish_reason=choice.get("finish_reason"),
            usage={
                **{k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage},
                **({"reasoning_tokens": reasoning_tokens} if reasoning_tokens is not None else {}),
            },
            cost=usage.get("cost"),
            latency_ms=latency_ms,
        )

    async def list_models(self) -> list[str]:
        """Public model list. Does not require the API key."""
        async with httpx.AsyncClient(timeout=20) as http:
            response = await http.get(f"{self._base_url}/models", headers=self._headers)
        response.raise_for_status()
        return sorted(item["id"] for item in response.json().get("data", []) if "id" in item)


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _error_from_response(status: int, data: dict[str, Any], model: str) -> LLMError:
    error = data.get("error") if isinstance(data.get("error"), dict) else {}
    detail = str(error.get("message") or "")[:300]
    code = error.get("code") or status
    logger.warning("OpenRouter request failed: status=%s code=%s model=%s", status, code, model)

    if status == 429 or code == 429:
        # Free models: about 20 requests/minute and a daily request cap.
        return LLMError("rate_limit", f"OpenRouter rate limit reached. {detail}".strip(), retryable=True)
    if status in (401, 403) or code in (401, 403):
        return LLMError("authentication", "OpenRouter rejected the API key (check OPENROUTER_API_KEY).")
    if status == 402 or code == 402:
        return LLMError("insufficient_credits", "OpenRouter account has insufficient credits.")
    if status == 404 or (status == 400 and "model" in detail.lower()):
        return LLMError("invalid_model", f"Invalid or unavailable model '{model}'. {detail}".strip())
    if status == 408:
        return LLMError("timeout", f"The request to model '{model}' timed out.", retryable=True)
    if status >= 500 or code in (502, 503):
        return LLMError("provider_error", f"The model provider returned an error ({code}). {detail}".strip(), retryable=True)
    return LLMError("api_error", f"OpenRouter request failed ({code}). {detail}".strip())


async def complete_with_retries(
    client: LLMClient,
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: float,
    max_attempts: int,
    reasoning_effort: str | None = None,
    json_output: bool = False,
) -> Completion:
    """Call the model, retrying retryable errors with exponential backoff."""
    attempt = 0
    while True:
        attempt += 1
        try:
            completion = await client.complete(
                model,
                messages,
                temperature,
                max_tokens,
                timeout,
                reasoning_effort=reasoning_effort,
                json_output=json_output,
            )
            completion.attempts = attempt
            return completion
        except LLMError as exc:
            if not exc.retryable or attempt >= max_attempts:
                raise
            delay = RATE_LIMIT_BACKOFF_SECONDS * attempt if exc.kind == "rate_limit" else 2**attempt
            logger.info("Retrying %s after %s error in %ss (attempt %s)", model, exc.kind, delay, attempt)
            await asyncio.sleep(delay)
