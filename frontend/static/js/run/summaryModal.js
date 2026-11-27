// Experiment Summary shown before a run starts.
// Rendered from the frozen snapshot returned by the server (the exact config the run will use).

import { h } from "../core/dom.js";
import { formatDateTime, capitalize } from "../core/format.js";
import { icon } from "../core/icons.js";
import { openOverlay } from "../core/overlay.js";
import { personaList } from "./personaView.js";

function metaCell(label, value, mono = false) {
  return h("div", null, h("div", { class: "label", text: label }), h("div", { class: `value ${mono ? "mono" : ""}`, text: String(value) }));
}

function agentBlock(agent, schema) {
  const isHuman = agent.agent_type === "human_simulation";
  return h(
    "div",
    { class: "summary-agent" },
    h(
      "div",
      { class: "summary-agent-head" },
      h("span", { class: `avatar-icon ${isHuman ? "avatar-human" : "avatar-robot"}` }, icon(isHuman ? "person" : "robot")),
      h("span", { class: "agent-name", text: agent.name }),
      h("span", { class: "model-pill", text: agent.persona_agent.model })
    ),
    personaList(schema.persona_agent_fields, agent.persona_agent, { skip: ["name"] }),
    isHuman
      ? [h("div", { class: "summary-subtitle", text: "Human Persona" }), personaList(schema.persona_human_fields, agent.persona_human)]
      : null
  );
}

export function openSummaryModal({ snapshot, schema, onConfirm, onCancel }) {
  const config = snapshot.configuration;

  const body = h(
    "div",
    null,
    h(
      "div",
      { class: "summary-meta" },
      metaCell("User", snapshot.username),
      metaCell("Run name", config.label || "—"),
      metaCell("Rounds", config.rounds),
      metaCell("Ordering", capitalize(config.ordering)),
      metaCell("AI Agents", config.agents.length),
      metaCell("Total turns", snapshot.total_turns),
      metaCell("Run ID", snapshot.run_id, true)
    ),
    h(
      "div",
      { class: "summary-section" },
      h("h3", { text: "Scenario" }),
      config.scenario ? h("div", { class: "scenario-block", text: config.scenario }) : h("p", { class: "muted", text: "No scenario." })
    ),
    h(
      "div",
      { class: "summary-section" },
      h("h3", { text: "Initial Message" }),
      h("div", { class: "quote", text: config.initial_message }),
      h("p", { class: "field-help", style: { marginTop: "8px" }, text: `Sent by ${config.human_agent.name} as the first turn of round 1.` })
    ),
    h("div", { class: "summary-section" }, h("h3", { text: "Human Agent" }), agentBlock(config.human_agent, schema)),
    h("div", { class: "summary-section" }, h("h3", { text: "AI Agents" }), config.agents.map((agent) => agentBlock(agent, schema))),
    h(
      "div",
      { class: "summary-section" },
      h("h3", { text: "Other Parameters" }),
      h(
        "dl",
        { class: "kv" },
        h("dt", { text: "LLM provider" }),
        h("dd", { text: config.llm_provider }),
        h("dt", { text: "Temperature" }),
        h("dd", { text: String(config.generation.temperature) }),
        h("dt", { text: "Max tokens" }),
        h("dd", { text: String(config.generation.max_tokens) }),
        h("dt", { text: "Rubric scoring" }),
        h("dd", { text: snapshot.rubric_enabled ? "On (after the run)" : "Off" }),
        h("dt", { text: "Random seed" }),
        h("dd", { class: "mono", text: String(config.random_seed) }),
        h("dt", { text: "Prepared at" }),
        h("dd", { text: formatDateTime(snapshot.created_at) })
      )
    )
  );

  const cancelBtn = h("button", { class: "btn", type: "button" }, "Cancel");
  const confirmBtn = h("button", { class: "btn btn-primary", type: "button" }, icon("play"), "Confirm and Run");

  let confirmed = false;
  const overlay = openOverlay({
    title: "Experiment Summary",
    body,
    footer: [cancelBtn, confirmBtn],
    onClose: (reason) => {
      if (!confirmed) onCancel();
    },
  });

  cancelBtn.addEventListener("click", () => overlay.close("cancel"));
  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    confirmBtn.replaceChildren(h("span", { class: "spinner" }), "Starting…");
    const ok = await onConfirm();
    if (ok) {
      confirmed = true;
      overlay.close("confirm");
    } else {
      confirmBtn.disabled = false;
      cancelBtn.disabled = false;
      confirmBtn.replaceChildren(icon("play"), "Confirm and Run");
    }
  });
}

/** Summary for a batch prepared on the server (one row per run). */
export function openBatchSummaryModal({ snapshot, onConfirm, onCancel }) {
  const rows = snapshot.runs.map((run, index) => {
    const config = run.configuration;
    const names = [config.human_agent.name, ...config.agents.map((agent) => agent.name)].join(" → ");
    return h(
      "tr",
      null,
      h("td", { class: "mono", text: String(index + 1) }),
      h("td", { text: config.label || "—" }),
      h("td", { text: `${config.rounds} · ${capitalize(config.ordering)}` }),
      h("td", { class: "names", text: names }),
      h("td", { class: "mono", text: String(run.total_turns) })
    );
  });

  const body = h(
    "div",
    null,
    h(
      "div",
      { class: "summary-meta" },
      metaCell("User", snapshot.username),
      metaCell("Runs", snapshot.size),
      metaCell("Total turns", snapshot.total_turns)
    ),
    h(
      "p",
      { class: "field-help", style: { marginTop: "12px" } },
      "Runs execute one after another and each is saved as its own result file. Stop ends the current run and skips the rest."
    ),
    h(
      "div",
      { class: "summary-section" },
      h("h3", { text: "Runs" }),
      h(
        "div",
        { class: "batch-table-wrap" },
        h(
          "table",
          { class: "batch-table" },
          h("thead", null, h("tr", null, ["#", "Run name", "Rounds · Ordering", "Speakers", "Turns"].map((t) => h("th", { text: t })))),
          h("tbody", null, rows)
        )
      )
    )
  );

  const cancelBtn = h("button", { class: "btn", type: "button" }, "Cancel");
  const confirmBtn = h("button", { class: "btn btn-primary", type: "button" }, icon("play"), `Confirm and Run ${snapshot.size} runs`);
  let confirmed = false;
  const overlay = openOverlay({
    title: "Batch Summary",
    body,
    footer: [cancelBtn, confirmBtn],
    onClose: () => {
      if (!confirmed) onCancel();
    },
  });
  cancelBtn.addEventListener("click", () => overlay.close("cancel"));
  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    confirmBtn.replaceChildren(h("span", { class: "spinner" }), "Starting…");
    if (await onConfirm()) {
      confirmed = true;
      overlay.close("confirm");
    } else {
      confirmBtn.disabled = false;
      cancelBtn.disabled = false;
      confirmBtn.replaceChildren(icon("play"), `Confirm and Run ${snapshot.size} runs`);
    }
  });
}
