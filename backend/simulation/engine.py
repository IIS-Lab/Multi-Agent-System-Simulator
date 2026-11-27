"""Simulation engine.

    result = await run_simulation(config, llm_client)

The engine knows nothing about the web UI, sessions, or storage. It can be used
directly from scripts for batch experiments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from backend.openrouter.client import LLMClient, LLMError, complete_with_retries
from backend.simulation.ordering import ScheduledTurn, build_schedule
from backend.simulation.prompts import build_messages, build_system_prompt
from backend.simulation.types import (
    AIAgentConfig,
    HumanAgentConfig,
    RunConfiguration,
    SimulationError,
    SimulationResult,
    TranscriptEntry,
    UsageTotals,
)

logger = logging.getLogger(__name__)

TurnStartCallback = Callable[[ScheduledTurn, "HumanAgentConfig | AIAgentConfig"], None]
TurnCompleteCallback = Callable[[TranscriptEntry, int, int], None]
StopCheck = Callable[[], bool]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


async def run_simulation(
    config: RunConfiguration,
    llm: LLMClient,
    *,
    should_stop: StopCheck | None = None,
    on_turn_start: TurnStartCallback | None = None,
    on_turn_complete: TurnCompleteCallback | None = None,
) -> SimulationResult:
    """Run every scheduled turn. Stops early on a stop request or an unrecoverable error.

    Round 1, sequence 1 is always the Human Agent's configured initial message,
    so progress is `len(transcript) / config.total_turns` and never exceeds 100%.
    """
    schedule = build_schedule(config)
    agents = {agent.id: agent for agent in config.all_agents()}
    transcript: list[TranscriptEntry] = []
    usage = UsageTotals()
    errors: list[SimulationError] = []
    status, stop_reason = "completed", None
    started_at = utc_now()

    for turn in schedule:
        if should_stop and should_stop():
            status, stop_reason = "stopped", "Stopped by user."
            break

        agent = agents[turn.agent_id]
        if on_turn_start:
            on_turn_start(turn, agent)

        try:
            entry = await _run_turn(turn, agent, config, transcript, llm)
        except LLMError as exc:
            errors.append(_error(exc.kind, exc.message, turn))
            status, stop_reason = "failed", exc.message
            break
        except Exception as exc:  # keep the partial transcript on unexpected failures
            logger.exception("Unexpected error during simulation turn")
            errors.append(_error("internal_error", f"Unexpected error: {type(exc).__name__}", turn))
            status, stop_reason = "failed", "Unexpected internal error."
            break

        transcript.append(entry)
        usage.add(entry.usage, entry.cost)
        if on_turn_complete:
            on_turn_complete(entry, len(transcript), len(schedule))

    return SimulationResult(
        status=status,
        stop_reason=stop_reason,
        started_at=started_at,
        completed_at=utc_now(),
        total_turns=len(schedule),
        completed_turns=len(transcript),
        transcript=transcript,
        usage=usage,
        errors=errors,
    )


async def _run_turn(
    turn: ScheduledTurn,
    agent: HumanAgentConfig | AIAgentConfig,
    config: RunConfiguration,
    transcript: list[TranscriptEntry],
    llm: LLMClient,
) -> TranscriptEntry:
    base = dict(
        round=turn.round,
        sequence=turn.sequence,
        position_in_round=turn.position_in_round,
        agent_id=agent.id,
        agent_name=agent.name,
        agent_type=agent.agent_type,
    )

    if turn.sequence == 1:
        # The experiment always opens with the Human Agent's configured message.
        return TranscriptEntry(
            **base,
            model=agent.persona_agent.model,
            content=config.initial_message,
            timestamp=utc_now(),
            source="initial_message",
        )

    messages = build_messages(build_system_prompt(agent, config), transcript, agent.id)
    completion = await complete_with_retries(
        llm,
        model=agent.persona_agent.model,
        messages=messages,
        temperature=config.generation.temperature,
        max_tokens=config.generation.max_tokens,
        timeout=config.generation.request_timeout_seconds,
        max_attempts=config.generation.max_attempts_per_turn,
        reasoning_effort=config.generation.reasoning_effort,
    )
    return TranscriptEntry(
        **base,
        model=agent.persona_agent.model,
        response_model=completion.model,
        content=completion.content,
        timestamp=utc_now(),
        source="generated",
        provider=completion.provider,
        generation_id=completion.generation_id,
        finish_reason=completion.finish_reason,
        latency_ms=completion.latency_ms,
        attempts=completion.attempts,
        usage=completion.usage,
        cost=completion.cost,
    )


def _error(kind: str, message: str, turn: ScheduledTurn) -> SimulationError:
    return SimulationError(
        kind=kind,
        message=message,
        round=turn.round,
        sequence=turn.sequence,
        agent_id=turn.agent_id,
        timestamp=utc_now(),
    )
