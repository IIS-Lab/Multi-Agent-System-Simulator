// Check Result page: scrollable list of saved result files, newest first.

import { api } from "../core/api.js";
import { h } from "../core/dom.js";
import { formatBytes, formatDateTime, formatRelative } from "../core/format.js";
import { mountHeader } from "../core/header.js";
import { icon } from "../core/icons.js";

const COLUMNS = ["", "File", "Run name", "Username", "Timestamp", ""];

async function init() {
  await mountHeader({ crumb: "Check Result" });
  const app = document.getElementById("app");

  const countText = h("p", { class: "sub", text: "Loading results…" });
  const refreshBtn = h("button", { class: "btn", type: "button" }, icon("refresh"), "Refresh");
  const scroll = h("div", { class: "result-scroll" });

  app.append(
    h(
      "div",
      { class: "page-head" },
      h("div", null, h("h1", { text: "Results" }), countText),
      h("div", { class: "actions" }, refreshBtn)
    ),
    h(
      "div",
      { class: "result-list-panel" },
      h("div", { class: "result-list-head" }, COLUMNS.map((label) => h("span", { text: label }))),
      scroll
    )
  );

  async function load() {
    refreshBtn.disabled = true;
    countText.textContent = "Loading results…";
    scroll.replaceChildren(...Array.from({ length: 6 }, () => h("div", { class: "skeleton-row" })));
    try {
      const { results } = await api("/api/results");
      countText.textContent = `${results.length} result${results.length === 1 ? "" : "s"} · newest first`;
      if (!results.length) {
        scroll.replaceChildren(
          h("div", { class: "list-state" }, icon("file"), h("strong", { text: "No results yet" }), "Results appear here after an experiment is saved.")
        );
      } else {
        scroll.replaceChildren(...results.map(resultRow));
      }
    } catch (error) {
      countText.textContent = "Could not load results.";
      scroll.replaceChildren(h("div", { class: "list-state" }, h("div", { class: "alert alert-danger" }, icon("alert"), h("span", { text: error.message }))));
    } finally {
      refreshBtn.disabled = false;
    }
  }

  refreshBtn.addEventListener("click", load);
  load();
}

function resultRow(result) {
  return h(
    "a",
    { class: "result-row", href: `/results/${encodeURIComponent(result.result_id)}` },
    h("span", { class: "file-icon" }, icon("file")),
    h("div", { style: { minWidth: "0" } }, h("div", { class: "filename", text: result.filename, title: result.filename }), h("div", { class: "size", text: formatBytes(result.size) })),
    h("span", { class: "cell", text: result.label || "—", title: result.label || undefined }),
    h("span", { class: "cell", text: result.username || "—" }),
    h(
      "span",
      { class: "cell" },
      result.timestamp ? formatDateTime(result.timestamp) : "—",
      result.timestamp ? h("span", { class: "rel", text: formatRelative(result.timestamp) }) : null
    ),
    icon("chevronRight", "chev")
  );
}

init();
