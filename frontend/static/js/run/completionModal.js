// Modal shown when a run finishes (completed, stopped or failed).
// Simulation status and storage (upload) status are shown separately.

import { h } from "../core/dom.js";
import { downloadJson } from "../core/format.js";
import { icon } from "../core/icons.js";
import { openOverlay } from "../core/overlay.js";

const OUTCOMES = {
  completed: { title: "Experiment completed.", icon: "checkCircle", tone: "done-success", badge: ["Completed", "badge-success"] },
  stopped: { title: "Experiment stopped.", icon: "stopCircle", tone: "done-warning", badge: ["Stopped", "badge-warning"] },
  failed: { title: "Experiment failed.", icon: "xCircle", tone: "done-danger", badge: ["Failed", "badge-danger"] },
};

const STORAGE_BADGES = {
  pending: ["Pending", ""],
  saving: ["Saving…", "badge-accent pulse"],
  saved: ["Saved", "badge-success"],
  failed: ["Upload failed", "badge-danger"],
};

export function openCompletionModal({ getRun, getDocument, onRetrySave, onCheckResult, onRunAgain }) {
  const checkBtn = h("button", { class: "btn", type: "button" }, icon("list"), "Check Result");
  const runBtn = h("button", { class: "btn btn-primary", type: "button" }, icon("play"), "Run Experiment");

  const overlay = openOverlay({
    title: "Experiment Finished",
    size: "sm",
    body: h("div"),
    footer: [checkBtn, runBtn],
    onClose: () => onRunAgain(),
  });

  checkBtn.addEventListener("click", () => onCheckResult());
  runBtn.addEventListener("click", () => overlay.close("run-again"));

  function render() {
    const run = getRun();
    const outcome = OUTCOMES[run.simulation_status] || OUTCOMES.failed;
    const [storageText, storageClass] = STORAGE_BADGES[run.storage_status] || STORAGE_BADGES.pending;
    const filename = run.storage_location ? run.storage_location.split("/").pop() : `${run.result_id}.json`;

    const extra = [];
    if (run.simulation_status === "failed" && run.error) {
      extra.push(h("div", { class: "alert alert-danger" }, icon("alert"), h("span", { text: run.error })));
    }
    if (run.storage_status === "saved") {
      extra.push(
        h(
          "div",
          { class: "path-box" },
          icon("file"),
          h("a", { class: "path-text", href: `/results/${encodeURIComponent(run.result_id)}`, title: "Open this result", text: run.storage_location }),
          run.storage_url ? h("a", { href: run.storage_url, target: "_blank", rel: "noopener", class: "icon-btn", title: "Open on GitHub" }, icon("external")) : null
        )
      );
    } else if (run.storage_status === "failed") {
      const retryBtn = h("button", { class: "btn btn-sm", type: "button" }, icon("refresh"), "Retry Save");
      retryBtn.addEventListener("click", async () => {
        retryBtn.disabled = true;
        retryBtn.replaceChildren(h("span", { class: "spinner" }), "Saving…");
        await onRetrySave();
        render();
      });
      const document_ = getDocument();
      extra.push(
        h("div", { class: "alert alert-warning" }, icon("alert"), h("span", { text: `Simulation finished, but the result upload failed. ${run.storage_error || ""}`.trim() })),
        h(
          "div",
          { class: "row" },
          document_ ? retryBtn : null,
          document_
            ? h("button", { class: "btn btn-sm", type: "button", onclick: () => downloadJson(filename, document_) }, icon("download"), "Download JSON")
            : null
        )
      );
    }

    overlay.setBody(
      h(
        "div",
        { class: "done-hero" },
        h("span", { class: `avatar-icon ${outcome.tone}` }, icon(outcome.icon)),
        h(
          "div",
          null,
          h("div", { class: "done-title", text: outcome.title }),
          h("div", { class: "done-sub", text: `${run.completed_turns} of ${run.total_turns} speaking turns recorded.` })
        )
      ),
      h(
        "div",
        { class: "status-rows" },
        h("div", { class: "status-row" }, h("span", { class: "label", text: "Simulation" }), h("span", { class: `badge ${outcome.badge[1]}`, text: outcome.badge[0] })),
        h("div", { class: "status-row" }, h("span", { class: "label", text: "Result upload" }), h("span", { class: `badge ${storageClass}`, text: storageText })),
        h("div", { class: "status-row" }, h("span", { class: "label", text: "Rubric score (0–1)" }), h("span", { class: "mono", text: formatScore(run.score) })),
        h("div", { class: "status-row" }, h("span", { class: "label", text: "Run ID" }), h("span", { class: "mono", text: run.run_id }))
      ),
      h("div", { class: "done-extra" }, extra)
    );
  }

  render();
  return { render, close: () => overlay.close() };
}

export function formatScore(score) {
  return typeof score === "number" ? score.toFixed(2) : "—";
}

/** Completion modal for a batch: one row per run, with retry for failed uploads. */
export function openBatchCompletionModal({ getBatch, onRetrySave, onCheckResult, onRunAgain }) {
  const checkBtn = h("button", { class: "btn", type: "button" }, icon("list"), "Check Result");
  const runBtn = h("button", { class: "btn btn-primary", type: "button" }, icon("play"), "Run Experiment");
  const overlay = openOverlay({ title: "Batch Finished", body: h("div"), footer: [checkBtn, runBtn], onClose: () => onRunAgain() });
  checkBtn.addEventListener("click", () => onCheckResult());
  runBtn.addEventListener("click", () => overlay.close("run-again"));

  function render() {
    const batch = getBatch();
    const counts = { completed: 0, stopped: 0, failed: 0, skipped: 0 };
    for (const run of batch.runs) counts[run.state === "skipped" ? "skipped" : run.simulation_status || "failed"] += 1;
    const uploadFailed = batch.runs.filter((run) => run.storage_status === "failed").length;
    const allGood = counts.completed === batch.size && !uploadFailed;
    const outcome = allGood ? OUTCOMES.completed : counts.failed ? OUTCOMES.failed : OUTCOMES.stopped;

    const rows = batch.runs.map((run, index) => {
      const sim = run.state === "skipped" ? ["Skipped", ""] : (OUTCOMES[run.simulation_status] || OUTCOMES.failed).badge;
      const [storageText, storageClass] = run.state === "skipped" ? ["—", ""] : STORAGE_BADGES[run.storage_status] || STORAGE_BADGES.pending;
      return h(
        "tr",
        null,
        h("td", { class: "mono", text: String(index + 1) }),
        h("td", { text: run.label || "—" }),
        h("td", null, h("span", { class: `badge ${sim[1]}`, text: sim[0] })),
        h("td", null, storageText === "—" ? "—" : h("span", { class: `badge ${storageClass}`, text: storageText })),
        h("td", { class: "mono", text: formatScore(run.score) }),
        h("td", null, run.storage_status === "saved" ? h("a", { href: `/results/${encodeURIComponent(run.result_id)}`, text: "Open" }) : "")
      );
    });

    const retryBtn = uploadFailed ? h("button", { class: "btn btn-sm", type: "button" }, icon("refresh"), `Retry ${uploadFailed} failed upload(s)`) : null;
    if (retryBtn) {
      retryBtn.addEventListener("click", async () => {
        retryBtn.disabled = true;
        retryBtn.replaceChildren(h("span", { class: "spinner" }), "Saving…");
        await onRetrySave();
        render();
      });
    }

    overlay.setBody(
      h(
        "div",
        { class: "done-hero" },
        h("span", { class: `avatar-icon ${outcome.tone}` }, icon(outcome.icon)),
        h(
          "div",
          null,
          h("div", { class: "done-title", text: allGood ? "Batch completed." : "Batch finished." }),
          h(
            "div",
            { class: "done-sub", text: `${counts.completed} completed · ${counts.stopped} stopped · ${counts.failed} failed · ${counts.skipped} skipped` }
          )
        )
      ),
      h(
        "div",
        { class: "batch-table-wrap", style: { marginTop: "18px" } },
        h(
          "table",
          { class: "batch-table" },
          h("thead", null, h("tr", null, ["#", "Run name", "Simulation", "Upload", "Score (0–1)", ""].map((t) => h("th", { text: t })))),
          h("tbody", null, rows)
        )
      ),
      retryBtn ? h("div", { class: "done-extra" }, retryBtn) : null
    );
  }

  render();
  return { render, close: () => overlay.close() };
}
