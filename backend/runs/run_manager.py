"""In-memory tracking of experiment runs and batches for the web app.

Run lifecycle:
  prepare()  -> state "prepared": run id created, configuration snapshot frozen
  start()    -> state "running":  simulation runs as a background task
  stop()     -> state "stopping": no new agent turns start
  scoring    -> state "scoring":  the rubric evaluator scores the transcript
  finished   -> state "finished": simulation_status + storage_status are set

A batch is a list of prepared runs executed one after another (e.g. from an
imported JSON file with several experiments or repeats). Each run in a batch
is saved as its own result file.

Simulation status (completed / stopped / failed) and storage status
(pending / saving / saved / failed) are tracked separately, so a finished
simulation is never lost because an upload failed.

Everything lives in this process's memory, so the app must run as a single
instance. Finished runs are kept for RETENTION_SECONDS so results can still be
fetched or re-saved from the browser.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.config import rubric
from backend.evaluation.evaluator import evaluate_transcript
from backend.openrouter.client import LLMClient
from backend.results.naming import build_result_id, new_run_id
from backend.results.schema import build_result_document
from backend.simulation.engine import run_simulation, utc_now
from backend.simulation.types import RunConfiguration, SimulationError, SimulationResult, TranscriptEntry, UsageTotals
from backend.storage.result_storage import ResultStorage, StorageError

logger = logging.getLogger(__name__)

PREPARED_TTL_SECONDS = 30 * 60
RETENTION_SECONDS = 24 * 60 * 60
MAX_BATCH_RUNS = 50
ACTIVE_STATES = ("running", "stopping", "scoring")


class RunError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class RunRecord:
    run_id: str
    result_id: str
    session_id: str
    username: str
    created_at: str
    configuration: RunConfiguration
    batch_id: str | None = None
    batch_index: int | None = None
    batch_size: int | None = None
    state: str = "prepared"  # prepared | running | stopping | scoring | finished | skipped
    simulation_status: str | None = None  # completed | stopped | failed
    storage_status: str = "pending"  # pending | saving | saved | failed
    storage_location: str | None = None
    storage_url: str | None = None
    storage_error: str | None = None
    completed_turns: int = 0
    current_turn: dict[str, Any] | None = None
    last_error: str | None = None
    document: dict[str, Any] | None = None
    score: float | None = None
    stop_requested: bool = False
    started_at: str | None = None
    partial_transcript: list[TranscriptEntry] = field(default_factory=list)
    touched_at: float = field(default_factory=time.monotonic)
    task: asyncio.Task | None = None

    @property
    def total_turns(self) -> int:
        return self.configuration.total_turns

    def batch_info(self) -> dict[str, Any] | None:
        if self.batch_id is None:
            return None
        return {"batch_id": self.batch_id, "index": self.batch_index, "size": self.batch_size}

    def snapshot(self) -> dict[str, Any]:
        """The frozen configuration snapshot shown in the Experiment Summary."""
        return {
            "run_id": self.run_id,
            "username": self.username,
            "created_at": self.created_at,
            "total_turns": self.total_turns,
            "rubric_enabled": rubric.RUBRIC_ENABLED,
            "configuration": self.configuration.model_dump(mode="json"),
        }

    def status(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "result_id": self.result_id,
            "label": self.configuration.label,
            "state": self.state,
            "simulation_status": self.simulation_status,
            "storage_status": self.storage_status,
            "storage_location": self.storage_location,
            "storage_url": self.storage_url,
            "storage_error": self.storage_error,
            "completed_turns": self.completed_turns,
            "total_turns": self.total_turns,
            "current_turn": self.current_turn,
            "score": self.score,
            "error": self.last_error,
        }


@dataclass
class BatchRecord:
    batch_id: str
    session_id: str
    username: str
    runs: list[RunRecord]
    state: str = "prepared"  # prepared | running | stopping | finished
    stop_requested: bool = False
    task: asyncio.Task | None = None
    touched_at: float = field(default_factory=time.monotonic)

    def current(self) -> RunRecord | None:
        return next((r for r in self.runs if r.state in ACTIVE_STATES), None)

    def status(self) -> dict[str, Any]:
        current = self.current()
        return {
            "batch_id": self.batch_id,
            "state": self.state,
            "size": len(self.runs),
            "current_index": current.batch_index if current else None,
            "completed_turns": sum(r.completed_turns for r in self.runs),
            "total_turns": sum(r.total_turns for r in self.runs),
            "finished_runs": sum(1 for r in self.runs if r.state in ("finished", "skipped")),
            "runs": [r.status() for r in self.runs],
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "username": self.username,
            "size": len(self.runs),
            "total_turns": sum(r.total_turns for r in self.runs),
            "rubric_enabled": rubric.RUBRIC_ENABLED,
            "runs": [r.snapshot() for r in self.runs],
        }


class RunManager:
    def __init__(self, llm: LLMClient, storage: ResultStorage):
        self._llm = llm
        self._storage = storage
        self._runs: dict[str, RunRecord] = {}
        self._batches: dict[str, BatchRecord] = {}

    @property
    def llm(self) -> LLMClient:
        return self._llm

    # -- lookup ----------------------------------------------------------

    def get(self, run_id: str, session_id: str) -> RunRecord:
        record = self._runs.get(run_id)
        if record is None or record.session_id != session_id:
            raise RunError("Run not found. It may have expired or the server was restarted.", 404)
        record.touched_at = time.monotonic()
        return record

    def get_batch(self, batch_id: str, session_id: str) -> BatchRecord:
        batch = self._batches.get(batch_id)
        if batch is None or batch.session_id != session_id:
            raise RunError("Batch not found. It may have expired or the server was restarted.", 404)
        batch.touched_at = time.monotonic()
        return batch

    def has_active_runs(self) -> bool:
        return any(r.state in ACTIVE_STATES for r in self._runs.values()) or any(
            b.state in ("running", "stopping") for b in self._batches.values()
        )

    def active_for_session(self, session_id: str) -> RunRecord | None:
        """Active stand-alone run (not part of a batch)."""
        for record in self._runs.values():
            if record.session_id == session_id and record.batch_id is None and record.state in ACTIVE_STATES:
                return record
        return None

    def active_batch_for_session(self, session_id: str) -> BatchRecord | None:
        for batch in self._batches.values():
            if batch.session_id == session_id and batch.state in ("running", "stopping"):
                return batch
        return None

    def _ensure_idle(self, session_id: str) -> None:
        if self.active_for_session(session_id) or self.active_batch_for_session(session_id):
            raise RunError("An experiment is already running in this session.", 409)

    # -- single runs -----------------------------------------------------

    def _new_record(self, session_id: str, username: str, configuration: RunConfiguration) -> RunRecord:
        created = datetime.now(timezone.utc)
        run_id = new_run_id()
        while run_id in self._runs:
            run_id = new_run_id()
        record = RunRecord(
            run_id=run_id,
            result_id=build_result_id(username, created, run_id, configuration.label),
            session_id=session_id,
            username=username,
            created_at=created.isoformat(timespec="seconds").replace("+00:00", "Z"),
            configuration=configuration,
        )
        self._runs[run_id] = record
        return record

    def prepare(self, session_id: str, username: str, configuration: RunConfiguration) -> RunRecord:
        self._purge_expired()
        self._ensure_idle(session_id)
        return self._new_record(session_id, username, configuration)

    def discard(self, run_id: str, session_id: str) -> None:
        record = self.get(run_id, session_id)
        if record.state == "prepared" and record.batch_id is None:
            del self._runs[run_id]

    def start(self, run_id: str, session_id: str) -> RunRecord:
        record = self.get(run_id, session_id)
        if record.state != "prepared" or record.batch_id is not None:
            raise RunError("This run has already been started.", 409)
        self._ensure_idle(session_id)
        record.state = "running"
        record.started_at = utc_now()
        record.task = asyncio.create_task(self._execute(record))
        return record

    def stop(self, run_id: str, session_id: str) -> RunRecord:
        record = self.get(run_id, session_id)
        if record.state == "running":
            record.stop_requested = True
            record.state = "stopping"
        return record

    async def retry_save(self, run_id: str, session_id: str) -> RunRecord:
        record = self.get(run_id, session_id)
        if record.state != "finished" or record.document is None:
            raise RunError("The run has not finished yet.", 409)
        if record.storage_status == "saved":
            return record
        if record.storage_status == "saving":
            raise RunError("The result is already being saved.", 409)
        await self._save(record)
        return record

    # -- batches ---------------------------------------------------------

    def prepare_batch(self, session_id: str, username: str, configurations: list[RunConfiguration]) -> BatchRecord:
        self._purge_expired()
        self._ensure_idle(session_id)
        if not configurations:
            raise RunError("The batch is empty.")
        if len(configurations) > MAX_BATCH_RUNS:
            raise RunError(f"A batch can contain at most {MAX_BATCH_RUNS} runs.")
        batch_id = f"batch_{secrets.token_hex(3)}"
        records = [self._new_record(session_id, username, config) for config in configurations]
        for index, record in enumerate(records, start=1):
            record.batch_id, record.batch_index, record.batch_size = batch_id, index, len(records)
        batch = BatchRecord(batch_id=batch_id, session_id=session_id, username=username, runs=records)
        self._batches[batch_id] = batch
        return batch

    def discard_batch(self, batch_id: str, session_id: str) -> None:
        batch = self.get_batch(batch_id, session_id)
        if batch.state == "prepared":
            for record in batch.runs:
                self._runs.pop(record.run_id, None)
            del self._batches[batch_id]

    def start_batch(self, batch_id: str, session_id: str) -> BatchRecord:
        batch = self.get_batch(batch_id, session_id)
        if batch.state != "prepared":
            raise RunError("This batch has already been started.", 409)
        self._ensure_idle(session_id)
        batch.state = "running"
        batch.task = asyncio.create_task(self._execute_batch(batch))
        return batch

    def stop_batch(self, batch_id: str, session_id: str) -> BatchRecord:
        batch = self.get_batch(batch_id, session_id)
        if batch.state == "running":
            batch.stop_requested = True
            batch.state = "stopping"
            current = batch.current()
            if current and current.state == "running":
                current.stop_requested = True
                current.state = "stopping"
        return batch

    async def retry_save_batch(self, batch_id: str, session_id: str) -> BatchRecord:
        batch = self.get_batch(batch_id, session_id)
        for record in batch.runs:
            if record.state == "finished" and record.document is not None and record.storage_status == "failed":
                await self._save(record)
        return batch

    async def _execute_batch(self, batch: BatchRecord) -> None:
        for record in batch.runs:
            if batch.stop_requested:
                record.state = "skipped"
                continue
            record.state = "running"
            record.started_at = utc_now()
            await self._execute(record)
        batch.state = "finished"

    # -- shutdown --------------------------------------------------------

    async def shutdown(self, timeout_seconds: float = 20) -> None:
        """Called when the server stops (e.g. a host restart).

        Active runs are interrupted and their partial transcripts are saved with
        status "failed", so the research log still shows how far they got.
        Runs of a batch that had not started yet are not saved.
        """
        active = [r for r in self._runs.values() if r.state in ACTIVE_STATES]
        if not active:
            return
        tasks = [r.task for r in active if r.task]
        tasks += [b.task for b in self._batches.values() if b.state in ("running", "stopping") and b.task]
        logger.warning("Server shutting down: interrupting %s active run(s)", len(active))
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        reason = "Interrupted because the server restarted."

        async def save_partial(record: RunRecord) -> None:
            if record.document is None:
                usage = UsageTotals()
                for entry in record.partial_transcript:
                    usage.add(entry.usage, entry.cost)
                result = SimulationResult(
                    status="failed",
                    stop_reason=reason,
                    started_at=record.started_at or record.created_at,
                    completed_at=utc_now(),
                    total_turns=record.total_turns,
                    completed_turns=len(record.partial_transcript),
                    transcript=record.partial_transcript,
                    usage=usage,
                    errors=[SimulationError(kind="server_restart", message=reason, timestamp=utc_now())],
                )
                record.simulation_status = "failed"
                record.last_error = reason
                record.document = self._document(record, result)
            if record.document.get("evaluation") is None and rubric.RUBRIC_ENABLED:
                record.document["evaluation"] = {"status": "failed", "error": reason}
            record.state = "finished"
            await self._save(record)

        try:
            await asyncio.wait_for(asyncio.gather(*(save_partial(r) for r in active)), timeout_seconds)
        except asyncio.TimeoutError:
            logger.error("Timed out while saving interrupted runs during shutdown")

    # -- internals -------------------------------------------------------

    def _document(self, record: RunRecord, result: SimulationResult) -> dict[str, Any]:
        return build_result_document(
            run_id=record.run_id,
            username=record.username,
            created_at=record.created_at,
            configuration=record.configuration,
            result=result,
            batch=record.batch_info(),
        )

    async def _execute(self, record: RunRecord) -> None:
        def on_turn_start(turn, agent) -> None:
            record.current_turn = {"round": turn.round, "sequence": turn.sequence, "agent_name": agent.name}

        def on_turn_complete(entry, completed, total) -> None:
            record.completed_turns = completed
            record.partial_transcript.append(entry)

        try:
            result = await run_simulation(
                record.configuration,
                self._llm,
                should_stop=lambda: record.stop_requested,
                on_turn_start=on_turn_start,
                on_turn_complete=on_turn_complete,
            )
            record.current_turn = None
            record.simulation_status = result.status
            record.last_error = result.stop_reason if result.status == "failed" else None
            record.document = self._document(record, result)

            if rubric.RUBRIC_ENABLED:
                record.state = "scoring"
                evaluation = await evaluate_transcript(self._llm, record.configuration, result.transcript)
                record.document["evaluation"] = evaluation
                record.score = ((evaluation.get("scores") or {}).get("overall") or {}).get("discounted")
        except asyncio.CancelledError:
            raise  # shutdown() saves the partial result
        except Exception:
            logger.exception("Run %s crashed", record.run_id)
            record.current_turn = None
            if record.document is None:
                record.simulation_status = "failed"
                record.last_error = "The simulation stopped because of an internal error."
                record.state = "finished"
                record.storage_status = "failed"
                record.storage_error = "No result document was produced."
                return
            record.document["evaluation"] = {"status": "failed", "error": "Internal error while scoring."}

        record.state = "finished"
        await self._save(record)

    async def _save(self, record: RunRecord) -> None:
        record.storage_status = "saving"
        record.storage_error = None
        try:
            saved = await self._storage.save_result(record.result_id, record.document)
        except StorageError as exc:
            record.storage_status = "failed"
            record.storage_error = str(exc)
            return
        except Exception:
            logger.exception("Unexpected storage failure for run %s", record.run_id)
            record.storage_status = "failed"
            record.storage_error = "Failed to save the result."
            return
        record.storage_status = "saved"
        record.storage_location = saved.location
        record.storage_url = saved.url

    def _purge_expired(self) -> None:
        now = time.monotonic()
        for batch_id, batch in list(self._batches.items()):
            age = now - batch.touched_at
            if (batch.state == "prepared" and age > PREPARED_TTL_SECONDS) or (
                batch.state == "finished" and age > RETENTION_SECONDS
            ):
                for record in batch.runs:
                    self._runs.pop(record.run_id, None)
                del self._batches[batch_id]
        for run_id, record in list(self._runs.items()):
            if record.batch_id is not None:
                continue
            age = now - record.touched_at
            if (record.state == "prepared" and age > PREPARED_TTL_SECONDS) or (
                record.state == "finished" and age > RETENTION_SECONDS
            ):
                del self._runs[run_id]
