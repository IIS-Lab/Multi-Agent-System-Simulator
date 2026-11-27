"""Experiment configuration metadata and run control endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from backend.auth.session import SessionUser, require_user
from backend.config import simulation_defaults as defaults
from backend.config.initial_message import INITIAL_MESSAGE
from backend.config.scenario import DEFAULT_SCENARIO, MAX_INITIAL_MESSAGE_LENGTH, MAX_SCENARIO_LENGTH
from backend.persona.fields import describe_fields
from backend.persona.generator import GenerationError, generate_persona_fields
from backend.persona.persona_agent import PersonaAgent
from backend.persona.persona_human import PersonaHuman
from backend.runs.config_builder import ConfigurationError, ExperimentRequest, build_run_configuration
from backend.runs.run_manager import MAX_BATCH_RUNS, RunError, RunManager

router = APIRouter(prefix="/api", tags=["experiment"])


def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


@router.get("/experiment/schema")
async def experiment_schema(user: SessionUser = Depends(require_user)):
    """Field definitions and limits used to build the Run Experiment page."""
    return {
        "persona_agent_fields": describe_fields(PersonaAgent),
        "persona_human_fields": describe_fields(PersonaHuman),
        "initial_message": INITIAL_MESSAGE,
        "default_scenario": DEFAULT_SCENARIO,
        "max_scenario_length": MAX_SCENARIO_LENGTH,
        "max_initial_message_length": MAX_INITIAL_MESSAGE_LENGTH,
        "default_rounds": defaults.DEFAULT_ROUNDS,
        "max_rounds": defaults.MAX_ROUNDS,
        "max_ai_agents": defaults.MAX_AI_AGENTS,
        "persona_generator_model": defaults.PERSONA_GENERATOR_MODEL,
    }


class GenerateRequest(BaseModel):
    target: Literal["persona_agent", "persona_human"]
    agent_kind: Literal["human", "ai"]
    fields: list[str] = []
    persona_agent: dict = {}
    scenario: str = Field("", max_length=MAX_SCENARIO_LENGTH)


@router.post("/persona/generate")
async def generate_persona(payload: GenerateRequest, request: Request, user: SessionUser = Depends(require_user)):
    """Fill generatable persona fields (e.g. Ethics, Human Persona) with model-generated text."""
    try:
        context = PersonaAgent.model_validate(payload.persona_agent)
    except ValidationError:
        context = None  # incomplete form: generate without context
    model_cls = PersonaAgent if payload.target == "persona_agent" else PersonaHuman
    try:
        values = await generate_persona_fields(
            request.app.state.run_manager.llm,
            model_cls=model_cls,
            field_names=payload.fields,
            agent_kind=payload.agent_kind,
            context=context,
            scenario=payload.scenario,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to generate persona text. {exc}")
    return {"values": values, "model": defaults.PERSONA_GENERATOR_MODEL}


@router.post("/runs/prepare")
async def prepare_run(
    payload: ExperimentRequest,
    request: Request,
    user: SessionUser = Depends(require_user),
    manager: RunManager = Depends(get_run_manager),
):
    """Validate the configuration, freeze a snapshot and return it for the Experiment Summary."""
    configurations = await _build_configurations(request, [payload])
    record = _call(lambda: manager.prepare(user.session_id, user.username, configurations[0]))
    return record.snapshot()


async def _build_configurations(request: Request, payloads: list[ExperimentRequest]):
    settings = request.app.state.settings
    configurations = []
    for index, payload in enumerate(payloads, start=1):
        try:
            configurations.append(build_run_configuration(payload, llm_provider=settings.llm_provider))
        except ConfigurationError as exc:
            prefix = f"Experiment {index}: " if len(payloads) > 1 else ""
            raise HTTPException(status_code=400, detail=f"{prefix}{exc}")

    if settings.llm_provider == "openrouter" and settings.openrouter_validate_models:
        models = sorted({a.persona_agent.model for c in configurations for a in c.all_agents()})
        unknown = await request.app.state.model_catalog.find_unknown(models)
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown OpenRouter model: {', '.join(unknown)}")
    return configurations


class BatchRequest(BaseModel):
    experiments: list[ExperimentRequest] = Field(min_length=1, max_length=MAX_BATCH_RUNS)


@router.post("/batches/prepare")
async def prepare_batch(
    payload: BatchRequest,
    request: Request,
    user: SessionUser = Depends(require_user),
    manager: RunManager = Depends(get_run_manager),
):
    """Freeze one configuration per run; the runs execute one after another."""
    configurations = await _build_configurations(request, payload.experiments)
    batch = _call(lambda: manager.prepare_batch(user.session_id, user.username, configurations))
    return batch.snapshot()


@router.post("/batches/{batch_id}/start")
async def start_batch(batch_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    return _call(lambda: manager.start_batch(batch_id, user.session_id)).status()


@router.post("/batches/{batch_id}/stop")
async def stop_batch(batch_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    return _call(lambda: manager.stop_batch(batch_id, user.session_id)).status()


@router.delete("/batches/{batch_id}")
async def discard_batch(batch_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    _call(lambda: manager.discard_batch(batch_id, user.session_id))
    return {"ok": True}


@router.get("/batches/{batch_id}")
async def batch_status(batch_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    return _call(lambda: manager.get_batch(batch_id, user.session_id)).status()


@router.post("/batches/{batch_id}/retry-save")
async def retry_save_batch(batch_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    try:
        batch = await manager.retry_save_batch(batch_id, user.session_id)
    except RunError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return batch.status()


@router.post("/runs/{run_id}/start")
async def start_run(run_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    return _call(lambda: manager.start(run_id, user.session_id)).status()


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    return _call(lambda: manager.stop(run_id, user.session_id)).status()


@router.delete("/runs/{run_id}")
async def discard_run(run_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    _call(lambda: manager.discard(run_id, user.session_id))
    return {"ok": True}


@router.get("/runs/active")
async def active_run(user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    record = manager.active_for_session(user.session_id)
    batch = manager.active_batch_for_session(user.session_id)
    return {
        "run": record.status() if record else None,
        "snapshot": record.snapshot() if record else None,
        "batch": batch.status() if batch else None,
    }


@router.get("/runs/{run_id}")
async def run_status(run_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    return _call(lambda: manager.get(run_id, user.session_id)).status()


@router.get("/runs/{run_id}/result")
async def run_result(run_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    record = _call(lambda: manager.get(run_id, user.session_id))
    if record.document is None:
        raise HTTPException(status_code=409, detail="The result is not available yet.")
    return record.document


@router.post("/runs/{run_id}/retry-save")
async def retry_save(run_id: str, user: SessionUser = Depends(require_user), manager: RunManager = Depends(get_run_manager)):
    try:
        record = await manager.retry_save(run_id, user.session_id)
    except RunError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return record.status()


def _call(action):
    try:
        return action()
    except RunError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
