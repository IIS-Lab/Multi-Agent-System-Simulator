"""Shared-password login with a signed session cookie.

The username is not an account; it only records who ran an experiment.
The password is compared on the server against APP_PASSWORD.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request

MAX_USERNAME_LENGTH = 64


@dataclass
class SessionUser:
    username: str
    session_id: str


def password_matches(candidate: str, expected: str) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def normalize_username(username: str) -> str:
    username = " ".join(username.split())
    if not username:
        raise ValueError("Please enter a username.")
    if len(username) > MAX_USERNAME_LENGTH:
        raise ValueError(f"Username must be at most {MAX_USERNAME_LENGTH} characters.")
    return username


def log_in(request: Request, username: str) -> SessionUser:
    request.session.clear()
    user = SessionUser(username=username, session_id=secrets.token_urlsafe(16))
    request.session.update({"username": user.username, "sid": user.session_id})
    return user


def log_out(request: Request) -> None:
    request.session.clear()


def current_user(request: Request) -> SessionUser | None:
    username = request.session.get("username")
    session_id = request.session.get("sid")
    if not username or not session_id:
        return None
    return SessionUser(username=username, session_id=session_id)


def require_user(request: Request) -> SessionUser:
    """FastAPI dependency for API routes that need a logged-in session."""
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user
