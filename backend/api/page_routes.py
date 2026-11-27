"""HTML page routes. Protected pages redirect to /login without a session."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from backend.auth.session import current_user
from backend.results.naming import is_valid_result_id
from backend.settings import PROJECT_ROOT

router = APIRouter(include_in_schema=False)

PAGES_DIR = PROJECT_ROOT / "frontend" / "pages"


def _page(name: str) -> FileResponse:
    return FileResponse(PAGES_DIR / f"{name}.html", headers={"Cache-Control": "no-store"})


def _protected(request: Request, name: str):
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    return _page(name)


@router.get("/")
async def root(request: Request):
    return RedirectResponse("/home" if current_user(request) else "/login", status_code=303)


@router.get("/login")
async def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/home", status_code=303)
    return _page("login")


@router.get("/home")
async def home_page(request: Request):
    return _protected(request, "home")


@router.get("/run")
async def run_page(request: Request):
    return _protected(request, "run")


@router.get("/results")
async def results_page(request: Request):
    return _protected(request, "results")


@router.get("/results/{result_id}")
async def result_page(result_id: str, request: Request):
    if not is_valid_result_id(result_id):
        return RedirectResponse("/results", status_code=303)
    return _protected(request, "result")
