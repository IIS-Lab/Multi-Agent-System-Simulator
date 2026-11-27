// Bottom-right panel: Progress bar and Start / Stop button.

import { h } from "../core/dom.js";
import { icon } from "../core/icons.js";

const PHASE_BADGES = {
  idle: ["Idle", ""],
  confirming: ["Confirming", "badge-accent"],
  running: ["Running", "badge-accent pulse"],
  stopping: ["Stopping", "badge-warning pulse"],
  completed: ["Completed", "badge-success"],
  stopped: ["Stopped", "badge-warning"],
  failed: ["Failed", "badge-danger"],
};

export function mountProgressPanel(body, badgeSlot, store, { onStart, onStop }) {
  const count = h("div", { class: "progress-count" });
  const percent = h("div", { class: "progress-percent" });
  const fill = h("div", { class: "progress-fill" });
  const status = h("div", { class: "progress-status" });
  const button = h("button", { class: "play-btn start", type: "button" });
  const label = h("div", { class: "run-control-label" });
  const badge = h("span", { class: "badge" });
  badgeSlot.replaceChildren(badge);

  button.addEventListener("click", () => {
    const { phase } = store.get();
    if (phase === "running") onStop();
    else if (phase !== "stopping" && phase !== "confirming") onStart();
  });

  body.replaceChildren(
    h(
      "div",
      { class: "progress-body" },
      h(
        "div",
        { class: "progress-info" },
        h("div", { class: "progress-numbers" }, count, percent),
        h("div", { class: "progress-track", role: "progressbar", "aria-label": "Progress" }, fill),
        status
      ),
      h("div", { class: "run-control" }, button, label)
    )
  );

  store.subscribe((state) => {
    const { phase, run, batch, draft } = state;
    const tracked = batch || run;
    const total = tracked ? tracked.total_turns : draft.rounds ? draft.rounds * (draft.agents.length + 1) : 0;
    const done = tracked ? Math.min(tracked.completed_turns, total) : 0;
    const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;

    count.replaceChildren(String(done), h("span", { class: "of", text: ` / ${total || "—"} turns` }));
    percent.textContent = `${pct}%`;
    fill.style.width = `${pct}%`;
    fill.className = `progress-fill ${phase === "completed" ? "done" : phase === "stopped" ? "halted" : phase === "failed" ? "error" : ""}`;
    fill.parentElement.setAttribute("aria-valuenow", String(pct));

    const [badgeText, badgeClass] = PHASE_BADGES[phase] || PHASE_BADGES.idle;
    badge.className = `badge ${badgeClass}`;
    badge.textContent = badgeText;

    status.replaceChildren(...statusLine(state));

    if (phase === "running") {
      button.className = "play-btn stop";
      button.replaceChildren(icon("stop"));
      button.disabled = false;
      button.setAttribute("aria-label", "Stop");
      label.textContent = "Stop";
    } else if (phase === "stopping" || phase === "confirming") {
      button.className = `play-btn ${phase === "stopping" ? "stop" : "start"}`;
      button.replaceChildren(h("span", { class: "spinner" }));
      button.disabled = true;
      label.textContent = phase === "stopping" ? "Stopping…" : "Preparing…";
    } else {
      button.className = "play-btn start";
      button.replaceChildren(icon("play"));
      button.disabled = !draft.rounds;
      button.setAttribute("aria-label", "Start");
      label.textContent = "Start";
    }
  });
}

/** The run currently executing (stand-alone or inside a batch) and its configuration. */
function currentRun({ run, batch, snapshot }) {
  if (batch) {
    const index = batch.current_index;
    if (!index) return { active: null, config: null, prefix: "" };
    const runSnapshot = snapshot && snapshot.runs ? snapshot.runs[index - 1] : null;
    return {
      active: batch.runs[index - 1],
      config: runSnapshot ? runSnapshot.configuration : null,
      prefix: `Run ${index} of ${batch.size} · `,
    };
  }
  return { active: run, config: snapshot ? snapshot.configuration : null, prefix: "" };
}

function statusLine(state) {
  const { phase, run, batch } = state;
  const { active, config, prefix } = currentRun(state);
  const current = active && active.current_turn;
  switch (phase) {
    case "running":
      if (active && active.state === "scoring") return [h("span", { class: "spinner" }), `${prefix}Scoring the transcript with the rubric…`];
      if (current) {
        const rounds = config ? config.rounds : "?";
        return [h("span", { class: "spinner" }), `${prefix}Round ${current.round} of ${rounds} · ${current.agent_name} is responding…`];
      }
      return [h("span", { class: "spinner" }), batch ? `${prefix}Starting…` : "Starting…"];
    case "stopping":
      return [h("span", { class: "spinner" }), "Waiting for the current turn to finish. No new turns will start."];
    case "confirming":
      return ["Review the Experiment Summary to start."];
    case "completed":
      return [batch ? "Batch completed." : "Experiment completed."];
    case "stopped":
      return ["Experiment stopped. The partial transcript was kept."];
    case "failed":
      return [run && run.error ? `Experiment failed: ${run.error}` : "Experiment failed."];
    default:
      return ["Ready. The run continues on the server even if you leave this page."];
  }
}
