import asyncio
import base64
import json

import httpx
import pytest

from backend.storage.github_storage import GitHubResultStorage
from backend.storage.result_storage import StorageError

RESULT_ID = "alice_2026-10-05T08-09-12_run_a83f2c"


def make_storage(responses, calls):
    storage = GitHubResultStorage(token="tok", owner="lab", repo="sim", branch="main", directory="results")

    async def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        status, body = responses.pop(0)
        content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return httpx.Response(status, content=content, request=httpx.Request(method, url))

    storage._request = fake_request
    return storage


def test_save_creates_new_file_without_sha():
    calls = []
    storage = make_storage([(201, {"content": {"html_url": "https://github.com/x"}})], calls)
    saved = asyncio.run(storage.save_result(RESULT_ID, {"run_id": "run_a83f2c"}))
    method, url, kwargs = calls[0]
    assert method == "PUT"
    assert url.endswith(f"/repos/lab/sim/contents/results/{RESULT_ID}.json")
    body = kwargs["json"]
    assert "sha" not in body and body["branch"] == "main"
    assert json.loads(base64.b64decode(body["content"]))["run_id"] == "run_a83f2c"
    assert saved.location == f"results/{RESULT_ID}.json"


def test_save_never_overwrites():
    storage = make_storage([(422, {"message": "sha wasn't supplied"})], [])
    with pytest.raises(StorageError, match="already exists"):
        asyncio.run(storage.save_result(RESULT_ID, {}))


def test_list_sorted_newest_first_and_missing_dir():
    items = [
        {"type": "file", "name": "bob_2026-10-04T10-00-00_run_111111.json", "size": 10},
        {"type": "file", "name": f"{RESULT_ID}.json", "size": 20},
        {"type": "file", "name": ".gitkeep", "size": 0},
    ]
    storage = make_storage([(200, items), (404, {})], [])
    listed = asyncio.run(storage.list_results())
    assert [r.result_id for r in listed] == [RESULT_ID, "bob_2026-10-04T10-00-00_run_111111"]
    assert listed[0].username == "alice"
    assert asyncio.run(storage.list_results()) == []


def test_errors_do_not_leak_token():
    storage = make_storage([(401, {"message": "Bad credentials"})], [])
    with pytest.raises(StorageError) as info:
        asyncio.run(storage.list_results())
    assert "tok" not in str(info.value)
