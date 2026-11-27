// Bottom-left panel: Run name, Rounds and Ordering.

import { h } from "../core/dom.js";
import { icon } from "../core/icons.js";
import { agentDisplayName, humanDisplayName, isBusy, parseRounds } from "./experimentState.js";

const ORDERINGS = [
  { value: "sequential", label: "Sequential", icon: "arrowsRight" },
  { value: "randomized", label: "Randomized", icon: "shuffle" },
];

export function mountRunSettings(body, store, { onChange }) {
  const { schema, draft } = store.get();

  const nameInput = h("input", {
    class: "input",
    id: "run-name",
    type: "text",
    maxlength: "100",
    autocomplete: "off",
    placeholder: "e.g. young_voices_nofac_6r",
    value: draft.label || "",
  });
  const nameHelp = h("div", { class: "field-help" });
  nameInput.addEventListener("input", () => onChange((current) => ({ ...current, label: nameInput.value })));

  const roundsInput = h("input", { id: "rounds", type: "text", inputmode: "numeric", value: draft.roundsText, "aria-label": "Rounds" });
  const minusBtn = h("button", { type: "button", "aria-label": "Decrease rounds" }, icon("minus"));
  const plusBtn = h("button", { type: "button", "aria-label": "Increase rounds" }, icon("plus"));
  const stepper = h("div", { class: "stepper" }, minusBtn, roundsInput, plusBtn);
  const roundsError = h("div", { class: "field-error", hidden: true });
  const roundsHelp = h("div", { class: "field-help" });

  function setRoundsText(text) {
    const { value, error } = parseRounds(text, schema.max_rounds);
    onChange((current) => ({ ...current, roundsText: text, rounds: error ? null : value }));
  }

  roundsInput.addEventListener("input", () => setRoundsText(roundsInput.value));
  minusBtn.addEventListener("click", () => {
    const current = store.get().draft.rounds || 1;
    roundsInput.value = String(Math.max(1, current - 1));
    setRoundsText(roundsInput.value);
  });
  plusBtn.addEventListener("click", () => {
    const current = store.get().draft.rounds || 0;
    roundsInput.value = String(Math.min(schema.max_rounds, current + 1));
    setRoundsText(roundsInput.value);
  });

  const segmentButtons = ORDERINGS.map((option) =>
    h(
      "button",
      {
        type: "button",
        role: "radio",
        "data-value": option.value,
        onclick: () => onChange((current) => ({ ...current, ordering: option.value })),
      },
      icon(option.icon),
      option.label
    )
  );
  const segmented = h("div", { class: "segmented", role: "radiogroup", "aria-label": "Ordering" }, segmentButtons);
  const preview = h("div", { class: "order-preview" });

  body.replaceChildren(
    h(
      "div",
      { class: "settings-body" },
      h("div", { class: "field" }, h("label", { class: "field-label", for: "run-name", text: "Run name" }), nameInput, nameHelp),
      h(
        "div",
        { class: "field" },
        h("label", { class: "field-label", for: "rounds", text: "Rounds" }),
        stepper,
        roundsError,
        roundsHelp
      ),
      h("div", { class: "field" }, h("span", { class: "field-label", text: "Ordering" }), segmented, preview)
    )
  );

  store.subscribe((state) => {
    const locked = isBusy(state.phase);
    const { draft } = state;
    const { error } = parseRounds(draft.roundsText, schema.max_rounds);

    nameInput.disabled = locked;
    if (document.activeElement !== nameInput && nameInput.value !== (draft.label || "")) nameInput.value = draft.label || "";
    const slug = fileSlug(draft.label);
    nameHelp.textContent = slug
      ? `File: ${slug}--{user}_{time}_{run_id}.json`
      : draft.label?.trim()
        ? "Only letters, digits, - and _ go into the file name; this name is kept inside the JSON only."
        : "Optional. Starts the result file name, so you can tell runs apart.";

    roundsInput.disabled = locked;
    minusBtn.disabled = locked || !draft.rounds || draft.rounds <= 1;
    plusBtn.disabled = locked || (draft.rounds || 0) >= schema.max_rounds;
    stepper.classList.toggle("invalid", Boolean(error));
    roundsError.hidden = !error;
    roundsError.textContent = error || "";
    const speakers = draft.agents.length + 1;
    roundsHelp.hidden = Boolean(error);
    roundsHelp.textContent = `Times each agent speaks · ${draft.rounds ? draft.rounds * speakers : "—"} turns`;

    for (const button of segmentButtons) {
      button.setAttribute("aria-checked", String(button.dataset.value === draft.ordering));
      button.disabled = locked;
    }
    renderPreview(preview, draft);
  });
}

// Same rule as backend/results/naming.py sanitize_label.
function fileSlug(label) {
  return (label || "")
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^[-_]+|[-_]+$/g, "")
    .slice(0, 60)
    .replace(/[-_]+$/g, "");
}

function renderPreview(preview, draft) {
  const sep = () => icon("chevronRight", "order-sep");
  const items = [h("span", { class: "order-chip human", text: humanDisplayName(draft) })];
  if (draft.ordering === "sequential") {
    const names = draft.agents.map((agent, index) => agentDisplayName(agent, index));
    const shown = names.length > 4 ? [...names.slice(0, 3), "…", names[names.length - 1]] : names;
    for (const name of shown) items.push(sep(), h("span", { class: name === "…" ? "" : "order-chip", text: name }));
  } else {
    items.push(sep(), h("span", { class: "order-chip random", text: `${draft.agents.length} AI Agent${draft.agents.length > 1 ? "s" : ""}, shuffled each round` }));
  }
  preview.replaceChildren(...items);
}
