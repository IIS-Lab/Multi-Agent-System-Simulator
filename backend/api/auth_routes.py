from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.auth.session import current_user, log_in, log_out, normalize_username, password_matches
from backend.settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest, request: Request):
    settings = get_settings()
    try:
        username = normalize_username(payload.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not settings.app_password:
        raise HTTPException(status_code=503, detail="Login is not available: APP_PASSWORD is not set on the server.")
    if not password_matches(payload.password, settings.app_password):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    user = log_in(request, username)
    return {"username": user.username}


@router.post("/logout")
async def logout(request: Request):
    log_out(request)
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return {"username": user.username}
