// Single result page: metadata strip plus the complete JSON (and a readable transcript tab).

import { api } from "../core/api.js";
import { h } from "../core/dom.js";
import { capitalize, downloadJson, formatDateTime } from "../core/format.js";
import { mountHeader } from "../core/header.js";
import { icon } from "../core/icons.js";
import { toast } from "../core/overlay.js";
import { renderJson } from "./jsonViewer.js";
import { renderScores } from "./scoresView.js";
import { renderTranscript } from "./transcriptView.js";

const STATUS_CLASS = { completed: "badge-success", stopped: "badge-warning", failed: "badge-danger" };

async function init() {
  await mountHeader({ crumb: "Check Result" });
  const app = document.getElementById("app");
  const resultId = decodeURIComponent(window.location.pathname.split("/").pop());
  const filename = `${resultId}.json`;

  const backLink = h("a", { class: "back-link", href: "/results" }, icon("arrowLeft"), "Back to Results");
  const content = h("div", null, h("div", { class: "list-state" }, h("span", { class: "spinner" }), "Loading result…"));
  app.append(backLink, content);

  let doc;
  try {
    doc = await api(`/api/results/${encodeURIComponent(resultId)}`);
  } catch (error) {
    content.replaceChildren(h("div", { class: "list-state" }, h("div", { class: "alert alert-danger" }, icon("alert"), h("span", { text: error.message }))));
    return;
  }

  const copyBtn = h("button", { class: "btn", type: "button" }, icon("copy"), "Copy JSON");
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(doc, null, 2));
      toast("JSON copied to clipboard.", { kind: "success", timeout: 2500 });
    } catch {
      toast("Could not copy to the clipboard.");
    }
  });
  const downloadBtn = h("button", { class: "btn btn-dark", type: "button", onclick: () => downloadJson(filename, doc) }, icon("download"), "Download JSON");

  const config = doc.configuration || {};
  const transcript = Array.isArray(doc.transcript) ? doc.transcript : [];
  const usage = doc.usage || {};
  const evaluation = doc.evaluation || null;
  const scores = evaluation && evaluation.scores;
  const overall = scores && scores.overall ? scores.overall.discounted : null;
  const scoreText = typeof overall === "number" ? overall.toFixed(2) : evaluation ? capitalize(evaluation.status || "—") : "—";
  const metaItems = [
    ["Status", doc.status ? h("span", { class: `badge ${STATUS_CLASS[doc.status] || ""}`, text: capitalize(doc.status) }) : "—"],
    ["Username", doc.username ?? "—"],
    ["Run name", doc.label || config.label || "—"],
    ["Rubric score (0–1)", scoreText],
    ["Created", formatDateTime(doc.created_at)],
    ["Run ID", doc.run_id ?? "—"],
    ["Rounds", config.rounds ?? "—"],
    ["Ordering", capitalize(config.ordering || "") || "—"],
    ["AI Agents", Array.isArray(config.agents) ? config.agents.length : "—"],
    ["Turns", doc.progress ? `${doc.progress.completed_turns} / ${doc.progress.total_turns}` : transcript.length],
    ["Total tokens", usage.total_tokens ?? "—"],
  ];

  const viewSlot = h("div");
  const tabs = [
    { key: "json", label: "JSON", render: () => renderJson(doc) },
    { key: "transcript", label: "Transcript", render: () => renderTranscript(doc) },
    { key: "scores", label: "Scores", render: () => renderScores(doc) },
  ];
  const tabButtons = tabs.map((tab) =>
    h("button", { type: "button", role: "radio", "data-key": tab.key, onclick: () => selectTab(tab.key) }, tab.label)
  );
  function selectTab(key) {
    tabButtons.forEach((button) => button.setAttribute("aria-checked", String(button.dataset.key === key)));
    viewSlot.replaceChildren(tabs.find((tab) => tab.key === key).render());
  }

  content.replaceChildren(
    h(
      "div",
      { class: "page-head" },
      h("div", { style: { minWidth: "0" } }, h("h1", { class: "result-title", text: filename })),
      h("div", { class: "actions" }, copyBtn, downloadBtn)
    ),
    h(
      "div",
      { class: "meta-strip" },
      metaItems.map(([label, value]) =>
        h("div", null, h("div", { class: "label", text: label }), h("div", { class: "value" }, value instanceof Node ? value : String(value)))
      )
    ),
    h(
      "div",
      { class: "viewer" },
      h(
        "div",
        { class: "viewer-tabs" },
        h("div", { class: "segmented", role: "radiogroup", "aria-label": "View" }, tabButtons),
        h("span", { class: "info", text: `${transcript.length} transcript entries · complete file` })
      ),
      viewSlot
    )
  );
  selectTab("json");
}

init();
