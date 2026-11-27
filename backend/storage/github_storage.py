"""Stores result JSON files in a GitHub repository via the GitHub REST API.

Server-side only. The token is never logged, returned, or stored in results.
Existing files are never overwritten: creating a path that already exists fails.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from backend.results.naming import is_valid_result_id, parse_result_id, result_filename
from backend.storage.result_storage import ResultSummary, SavedResult, StorageError

logger = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"


class GitHubResultStorage:
    def __init__(self, token: str, owner: str, repo: str, branch: str, directory: str):
        self._token = token
        self._owner = owner
        self._repo = repo
        self._branch = branch
        self._directory = directory

    # -- helpers ---------------------------------------------------------

    def _check_configured(self) -> None:
        if not (self._token and self._owner and self._repo):
            raise StorageError(
                "GitHub storage is not configured. Set GITHUB_TOKEN, GITHUB_OWNER and GITHUB_REPO on the server."
            )

    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mass-simulator",
        }

    def _contents_url(self, path: str) -> str:
        return f"{API_ROOT}/repos/{self._owner}/{self._repo}/contents/{path}"

    def _path(self, result_id: str) -> str:
        return f"{self._directory}/{result_filename(result_id)}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                return await http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            logger.warning("GitHub request failed: %s %s", method, type(exc).__name__)
            raise StorageError("Could not reach the GitHub API.") from None

    @staticmethod
    def _raise_for_status(response: httpx.Response, action: str) -> None:
        if response.status_code < 400:
            return
        logger.warning("GitHub %s failed with status %s", action, response.status_code)
        if response.status_code == 401:
            raise StorageError("GitHub authentication failed. Check GITHUB_TOKEN.")
        if response.status_code == 403:
            raise StorageError("GitHub denied access. Check the token's repository permissions or rate limit.")
        if response.status_code == 404:
            raise StorageError("GitHub repository, branch or file not found.")
        raise StorageError(f"GitHub API error while trying to {action} (HTTP {response.status_code}).")

    # -- ResultStorage ---------------------------------------------------

    async def save_result(self, result_id: str, document: dict[str, Any]) -> SavedResult:
        self._check_configured()
        path = self._path(result_id)
        content = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        body = {
            "message": f"Add experiment result {result_id}",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": self._branch,
        }
        # No "sha" is sent, so GitHub refuses to overwrite an existing file (HTTP 422).
        response = await self._request("PUT", self._contents_url(path), headers=self._headers(), json=body)
        if response.status_code == 422:
            raise StorageError(f"A result file named {path} already exists. It was not overwritten.")
        self._raise_for_status(response, "save the result")
        html_url = (response.json().get("content") or {}).get("html_url")
        return SavedResult(result_id=result_id, location=path, url=html_url)

    async def list_results(self) -> list[ResultSummary]:
        self._check_configured()
        response = await self._request(
            "GET",
            self._contents_url(self._directory),
            headers=self._headers(),
            params={"ref": self._branch},
        )
        if response.status_code == 404:
            return []  # the results directory does not exist yet
        self._raise_for_status(response, "list results")

        items = response.json()
        summaries = []
        for item in items if isinstance(items, list) else []:
            name = item.get("name", "")
            if item.get("type") != "file" or not name.endswith(".json"):
                continue
            result_id = name[: -len(".json")]
            meta = parse_result_id(result_id) or {}
            summaries.append(
                ResultSummary(
                    result_id=result_id,
                    filename=name,
                    label=meta.get("label") or None,
                    username=meta.get("username"),
                    timestamp=meta.get("timestamp"),
                    run_id=meta.get("run_id"),
                    size=item.get("size"),
                )
            )
        summaries.sort(key=lambda s: (s.timestamp or "", s.filename), reverse=True)
        return summaries

    async def load_result(self, result_id: str) -> dict[str, Any]:
        self._check_configured()
        if not is_valid_result_id(result_id):
            raise StorageError("Invalid result id.")
        response = await self._request(
            "GET",
            self._contents_url(self._path(result_id)),
            headers=self._headers(accept="application/vnd.github.raw+json"),
            params={"ref": self._branch},
        )
        self._raise_for_status(response, "load the result")
        try:
            return json.loads(response.content)
        except ValueError:
            raise StorageError("The result file is not valid JSON.") from None
