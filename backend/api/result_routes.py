"""Read saved results (via the configured ResultStorage; GitHub by default)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth.session import SessionUser, require_user
from backend.results.naming import is_valid_result_id
from backend.storage.result_storage import StorageError

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("")
async def list_results(request: Request, user: SessionUser = Depends(require_user)):
    try:
        summaries = await request.app.state.storage.list_results()
    except StorageError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load results. {exc}")
    return {"results": [asdict(summary) for summary in summaries]}


@router.get("/{result_id}")
async def get_result(result_id: str, request: Request, user: SessionUser = Depends(require_user)):
    if not is_valid_result_id(result_id):
        raise HTTPException(status_code=400, detail="Invalid result id.")
    try:
        return await request.app.state.storage.load_result(result_id)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load the result. {exc}")
