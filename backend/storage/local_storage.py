"""Stores results as JSON files on the local disk (STORAGE_BACKEND=local).

Intended for local development and testing without a GitHub token.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from backend.results.naming import is_valid_result_id, parse_result_id, result_filename
from backend.storage.result_storage import ResultSummary, SavedResult, StorageError


class LocalResultStorage:
    def __init__(self, directory: Path):
        self._directory = directory

    async def save_result(self, result_id: str, document: dict[str, Any]) -> SavedResult:
        path = self._directory / result_filename(result_id)

        def write() -> None:
            self._directory.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as handle:  # "x" never overwrites
                json.dump(document, handle, indent=2, ensure_ascii=False)
                handle.write("\n")

        try:
            await asyncio.to_thread(write)
        except FileExistsError:
            raise StorageError(f"A result file named {path.name} already exists. It was not overwritten.") from None
        except OSError:
            raise StorageError("Failed to write the result file to local storage.") from None
        return SavedResult(result_id=result_id, location=f"{self._directory.name}/{path.name}")

    async def list_results(self) -> list[ResultSummary]:
        if not self._directory.exists():
            return []
        summaries = []
        for path in self._directory.glob("*.json"):
            meta = parse_result_id(path.stem) or {}
            summaries.append(
                ResultSummary(
                    result_id=path.stem,
                    filename=path.name,
                    label=meta.get("label") or None,
                    username=meta.get("username"),
                    timestamp=meta.get("timestamp"),
                    run_id=meta.get("run_id"),
                    size=path.stat().st_size,
                )
            )
        summaries.sort(key=lambda s: (s.timestamp or "", s.filename), reverse=True)
        return summaries

    async def load_result(self, result_id: str) -> dict[str, Any]:
        if not is_valid_result_id(result_id):
            raise StorageError("Invalid result id.")
        path = self._directory / result_filename(result_id)
        if not path.exists():
            raise StorageError("Result not found.")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            raise StorageError("The result file is not valid JSON.") from None
