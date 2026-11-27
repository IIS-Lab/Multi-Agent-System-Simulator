"""Result JSON document: one file per experiment run.

Top-level keys:
  schema_version, run_id, username, label, batch, created_at, started_at,
  completed_at, status, stop_reason, progress, configuration, transcript,
  usage, errors, evaluation

schema 1.1: adds label, batch, configuration.scenario, persona name/profile,
merged persona_human context, and the rubric "evaluation" section.
"""

from __future__ import annotations

from typing import Any

from backend.simulation.types import RunConfiguration, SimulationResult

SCHEMA_VERSION = "1.1"


def build_result_document(
    *,
    run_id: str,
    username: str,
    created_at: str,
    configuration: RunConfiguration,
    result: SimulationResult,
    batch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "username": username,
        "label": configuration.label,
        "batch": batch,
        "created_at": created_at,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "status": result.status,
        "stop_reason": result.stop_reason,
        "progress": {
            "completed_turns": result.completed_turns,
            "total_turns": result.total_turns,
        },
        "configuration": configuration.model_dump(mode="json"),
        "transcript": [entry.model_dump(mode="json") for entry in result.transcript],
        "usage": result.usage.model_dump(mode="json"),
        "errors": [error.model_dump(mode="json") for error in result.errors],
        "evaluation": None,
    }
