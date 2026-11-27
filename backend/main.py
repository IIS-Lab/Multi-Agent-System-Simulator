"""FastAPI application entry point.

Run locally:  uvicorn backend.main:app --reload
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from backend.api import auth_routes, experiment_routes, page_routes, result_routes
from backend.openrouter.client import OpenRouterClient
from backend.openrouter.mock_client import MockLLMClient
from backend.openrouter.model_catalog import ModelCatalog
from backend.runs.keep_alive import is_public_url, keep_alive_loop
from backend.runs.run_manager import RunManager
from backend.settings import PROJECT_ROOT, get_settings
from backend.storage.result_storage import get_result_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs full request URLs at INFO; keep it quiet.
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        keep_alive = None
        if settings.keep_alive_while_running and is_public_url(settings.app_public_url):
            keep_alive = asyncio.create_task(keep_alive_loop(settings.app_public_url, app.state.run_manager.has_active_runs))
        yield
        if keep_alive:
            keep_alive.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await keep_alive
        # Save partial results of runs interrupted by a restart or redeploy.
        await app.state.run_manager.shutdown()

    app = FastAPI(title="Multi Agent System Simulator", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    openrouter = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        app_url=settings.app_public_url,
    )
    llm = MockLLMClient() if settings.llm_provider == "mock" else openrouter
    storage = get_result_storage(settings)

    app.state.settings = settings
    app.state.storage = storage
    app.state.model_catalog = ModelCatalog(openrouter)
    app.state.run_manager = RunManager(llm=llm, storage=storage)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="mas_session",
        max_age=14 * 24 * 3600,
        same_site="lax",
        https_only=settings.session_cookie_secure,
    )

    @app.middleware("http")
    async def revalidate_static_files(request: Request, call_next):
        # Make browsers check for a newer version of JS/CSS on every page load,
        # so a redeploy is picked up without a hard refresh.
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"ok": True}

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": _format_validation_errors(exc)})

    app.include_router(auth_routes.router)
    app.include_router(experiment_routes.router)
    app.include_router(result_routes.router)
    app.include_router(page_routes.router)
    app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "frontend" / "static"), name="static")
    return app


def _format_validation_errors(exc: RequestValidationError) -> str:
    """Readable English message, e.g. 'Invalid configuration: agents → 1 → persona_agent → age: ...'."""
    parts = []
    for error in exc.errors()[:5]:
        location = [str(p) for p in error.get("loc", []) if p != "body"]
        # Show agent positions as 1-based numbers to match "Agent 1", "Agent 2", ...
        if len(location) >= 2 and location[0] == "agents" and location[1].isdigit():
            location[1] = f"Agent {int(location[1]) + 1}"
        prefix = " → ".join(location)
        parts.append(f"{prefix}: {error.get('msg', 'Invalid value')}" if prefix else error.get("msg", ""))
    return "Invalid configuration. " + "; ".join(parts)


app = create_app()
