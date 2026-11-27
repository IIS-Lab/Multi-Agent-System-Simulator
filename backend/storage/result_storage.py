"""Result storage interface.

The simulation engine never writes results itself. The run manager hands a
finished result document to a `ResultStorage`. To move results to S3, R2,
Supabase or a database, add a class with these three methods and return it
from `get_result_storage`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.settings import Settings


class StorageError(Exception):
    """Safe, user-facing storage error (never contains tokens)."""


@dataclass
class SavedResult:
    result_id: str
    location: str  # e.g. "results/alice_..._run_a83f2c.json"
    url: str | None = None  # browsable link, if any


@dataclass
class ResultSummary:
    result_id: str
    filename: str
    username: str | None
    timestamp: str | None
    run_id: str | None
    size: int | None = None
    label: str | None = None


class ResultStorage(Protocol):
    async def save_result(self, result_id: str, document: dict[str, Any]) -> SavedResult: ...

    async def list_results(self) -> list[ResultSummary]: ...

    async def load_result(self, result_id: str) -> dict[str, Any]: ...


def get_result_storage(settings: Settings) -> ResultStorage:
    if settings.storage_backend == "local":
        from backend.storage.local_storage import LocalResultStorage

        return LocalResultStorage(settings.local_results_dir)

    from backend.storage.github_storage import GitHubResultStorage

    return GitHubResultStorage(
        token=settings.github_token,
        owner=settings.github_owner,
        repo=settings.github_repo,
        branch=settings.github_branch,
        directory=settings.github_results_dir,
    )
