// Run lifecycle on the Run Experiment page.
//
// Single run: Start -> prepare (server freezes snapshot) -> Experiment Summary
//             -> Confirm and Run -> poll progress -> completion modal.
// Batch:      Import JSON with several runs -> prepare batch -> Batch Summary
//             -> Confirm -> poll batch progress -> batch completion modal.

import { api } from "../core/api.js";
import { toast } from "../core/overlay.js";
import { openBatchCompletionModal, openCompletionModal } from "./completionModal.js";
import { experimentFromDraft, toExperimentRequest } from "./experimentState.js";
import { openBatchSummaryModal, openSummaryModal } from "./summaryModal.js";

const POLL_INTERVAL_MS = 1000;

export function createRunController(store) {
  let pollTimer = null;
  let pollFailures = 0;
  let resultDocument = null;

  const resetRunState = () => store.update({ phase: "idle", run: null, batch: null, snapshot: null });
  const goToResults = () => (window.location.href = "/results");

  // ---- single run ------------------------------------------------------

  async function start() {
    const { draft, schema, phase } = store.get();
    if (phase === "running" || phase === "stopping" || phase === "confirming") return;
    if (!draft.rounds) {
      toast("Please enter a valid number of rounds.");
      return;
    }

    store.update({ phase: "confirming", run: null, batch: null, snapshot: null });
    let snapshot;
    try {
      snapshot = await api("/api/runs/prepare", { method: "POST", body: toExperimentRequest(draft) });
    } catch (error) {
      store.update({ phase: "idle" });
      toast(error.message);
      return;
    }
    store.update({ snapshot });

    openSummaryModal({
      snapshot,
      schema,
      onCancel: () => {
        api(`/api/runs/${snapshot.run_id}`, { method: "DELETE" }).catch(() => {});
        resetRunState();
      },
      onConfirm: async () => {
        try {
          const run = await api(`/api/runs/${snapshot.run_id}/start`, { method: "POST" });
          store.update({ phase: "running", run });
          beginPolling(() => pollRun(snapshot.run_id));
          return true;
        } catch (error) {
          toast(error.message);
          return false;
        }
      },
    });
  }

  async function pollRun(runId) {
    const status = await fetchStatus(`/api/runs/${runId}`);
    if (!status) return;
    if (status.state === "finished") {
      if (status.storage_status === "saving" || status.storage_status === "pending") {
        store.update({ run: status });
        return;
      }
      stopPolling();
      await finishRun(status);
      return;
    }
    store.update({ run: status, phase: status.state === "stopping" ? "stopping" : "running" });
  }

  async function finishRun(status) {
    // Keep the result in the browser so it survives an upload failure.
    try {
      resultDocument = await api(`/api/runs/${status.run_id}/result`);
    } catch {
      resultDocument = null;
    }
    store.update({ run: status, phase: status.simulation_status || "failed" });

    openCompletionModal({
      getRun: () => store.get().run,
      getDocument: () => resultDocument,
      onRetrySave: async () => {
        try {
          const updated = await api(`/api/runs/${status.run_id}/retry-save`, { method: "POST" });
          store.update({ run: updated });
          if (updated.storage_status === "failed") toast(updated.storage_error || "Failed to save the result.");
        } catch (error) {
          toast(error.message);
        }
      },
      onCheckResult: goToResults,
      onRunAgain: () => {
        // Keep the current agent configuration; reset run progress and result state.
        resultDocument = null;
        resetRunState();
      },
    });
  }

  // ---- batch -----------------------------------------------------------

  /** experiments: [{ draft, repeats }] from an imported file. */
  async function startBatch(experiments) {
    const { phase } = store.get();
    if (phase === "running" || phase === "stopping" || phase === "confirming") return;
    const requests = experiments.flatMap(({ draft, repeats }) => Array.from({ length: repeats }, () => experimentFromDraft(draft)));

    store.update({ phase: "confirming", run: null, batch: null, snapshot: null });
    let snapshot;
    try {
      snapshot = await api("/api/batches/prepare", { method: "POST", body: { experiments: requests } });
    } catch (error) {
      store.update({ phase: "idle" });
      toast(error.message);
      return;
    }
    store.update({ snapshot });

    openBatchSummaryModal({
      snapshot,
      onCancel: () => {
        api(`/api/batches/${snapshot.batch_id}`, { method: "DELETE" }).catch(() => {});
        resetRunState();
      },
      onConfirm: async () => {
        try {
          const batch = await api(`/api/batches/${snapshot.batch_id}/start`, { method: "POST" });
          store.update({ phase: "running", batch });
          beginPolling(() => pollBatch(snapshot.batch_id));
          return true;
        } catch (error) {
          toast(error.message);
          return false;
        }
      },
    });
  }

  async function pollBatch(batchId) {
    const status = await fetchStatus(`/api/batches/${batchId}`);
    if (!status) return;
    const saving = status.runs.some((run) => run.storage_status === "saving");
    if (status.state === "finished" && !saving) {
      stopPolling();
      const anyFailed = status.runs.some((run) => run.simulation_status === "failed");
      const anyStopped = status.runs.some((run) => run.state === "skipped" || run.simulation_status === "stopped");
      store.update({ batch: status, phase: anyFailed ? "failed" : anyStopped ? "stopped" : "completed" });
      openBatchCompletionModal({
        getBatch: () => store.get().batch,
        onRetrySave: async () => {
          try {
            store.update({ batch: await api(`/api/batches/${batchId}/retry-save`, { method: "POST" }) });
          } catch (error) {
            toast(error.message);
          }
        },
        onCheckResult: goToResults,
        onRunAgain: resetRunState,
      });
      return;
    }
    store.update({ batch: status, phase: status.state === "stopping" ? "stopping" : "running" });
  }

  // ---- shared ----------------------------------------------------------

  async function stop() {
    const { run, batch } = store.get();
    if (!run && !batch) return;
    store.update({ phase: "stopping" });
    try {
      if (batch) store.update({ batch: await api(`/api/batches/${batch.batch_id}/stop`, { method: "POST" }) });
      else store.update({ run: await api(`/api/runs/${run.run_id}/stop`, { method: "POST" }) });
    } catch (error) {
      toast(error.message);
    }
  }

  async function fetchStatus(path) {
    try {
      const status = await api(path);
      pollFailures = 0;
      return status;
    } catch (error) {
      pollFailures += 1;
      if (error.status === 404) {
        stopPolling();
        toast(error.message);
        store.update({ phase: "failed" });
      } else if (pollFailures === 5) {
        toast("Lost connection to the server. Still retrying…");
      }
      return null;
    }
  }

  function beginPolling(poll) {
    stopPolling();
    pollFailures = 0;
    pollTimer = setInterval(poll, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    clearInterval(pollTimer);
    pollTimer = null;
  }

  /** Resume a run or batch that is still active on the server (e.g. after a page reload). */
  async function resumeIfActive() {
    try {
      const { run, snapshot, batch } = await api("/api/runs/active");
      if (batch) {
        store.update({ phase: batch.state === "stopping" ? "stopping" : "running", batch, run: null, snapshot: null });
        beginPolling(() => pollBatch(batch.batch_id));
      } else if (run) {
        store.update({ phase: run.state === "stopping" ? "stopping" : "running", run, batch: null, snapshot });
        beginPolling(() => pollRun(run.run_id));
      }
    } catch {
      /* nothing to resume */
    }
  }

  return { start, startBatch, stop, resumeIfActive };
}
