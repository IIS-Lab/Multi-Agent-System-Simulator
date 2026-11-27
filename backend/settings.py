"""Server-side settings loaded from environment variables.

Secrets (APP_PASSWORD, OPENROUTER_API_KEY, GITHUB_TOKEN, SESSION_SECRET) are only
read here and must never be sent to the browser, written into results, or logged.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load a local .env file if present (development). In production, set real env vars.
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_password: str
    session_secret: str
    session_cookie_secure: bool

    llm_provider: str  # "openrouter" or "mock"
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_validate_models: bool
    app_public_url: str
    keep_alive_while_running: bool

    storage_backend: str  # "github" or "local"
    github_token: str
    github_owner: str
    github_repo: str
    github_branch: str
    github_results_dir: str
    local_results_dir: Path

    @property
    def github_configured(self) -> bool:
        return bool(self.github_token and self.github_owner and self.github_repo)


@lru_cache
def get_settings() -> Settings:
    session_secret = _env("SESSION_SECRET")
    if not session_secret:
        session_secret = secrets.token_urlsafe(32)
        logger.warning(
            "SESSION_SECRET is not set. Using a random secret; all sessions "
            "will be invalidated when the server restarts."
        )

    return Settings(
        app_password=_env("APP_PASSWORD"),
        session_secret=session_secret,
        session_cookie_secure=_env_bool("SESSION_COOKIE_SECURE", False),
        llm_provider=_env("LLM_PROVIDER", "openrouter").lower(),
        openrouter_api_key=_env("OPENROUTER_API_KEY"),
        openrouter_base_url=_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
        openrouter_validate_models=_env_bool("OPENROUTER_VALIDATE_MODELS", True),
        app_public_url=_env("APP_PUBLIC_URL", "http://localhost:8000"),
        keep_alive_while_running=_env_bool("KEEP_ALIVE_WHILE_RUNNING", True),
        storage_backend=_env("STORAGE_BACKEND", "github").lower(),
        github_token=_env("GITHUB_TOKEN"),
        github_owner=_env("GITHUB_OWNER"),
        github_repo=_env("GITHUB_REPO"),
        github_branch=_env("GITHUB_BRANCH", "main"),
        github_results_dir=_env("GITHUB_RESULTS_DIR", "results").strip("/"),
        local_results_dir=PROJECT_ROOT / _env("LOCAL_RESULTS_DIR", "local_results"),
    )
