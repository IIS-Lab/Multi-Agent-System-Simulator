// Scenario editor: shared Scenario (setting and rules every agent
// sees) and the Initial Message the Human Agent opens with. Applied only on Save.

import { h } from "../core/dom.js";
import { icon } from "../core/icons.js";
import { openOverlay } from "../core/overlay.js";

export function openScenarioEditor({ schema, draft, humanName, onSave }) {
  const scenario = h("textarea", {
    class: "textarea",
    id: "exp-scenario",
    rows: 12,
    maxlength: String(schema.max_scenario_length),
    placeholder: "Setting, topic and shared rules of the conversation. Every agent sees this.",
    value: draft.scenario || "",
  });
  const initial = h("textarea", {
    class: "textarea",
    id: "exp-initial",
    rows: 4,
    maxlength: String(schema.max_initial_message_length),
    value: draft.initialMessage || "",
  });
  const initialError = h("div", { class: "field-error", hidden: true });

  const body = h(
    "div",
    { class: "scenario-form" },
    h(
      "div",
      { class: "field" },
      h("label", { class: "field-label", for: "exp-scenario", text: "Scenario" }),
      scenario,
      h("div", { class: "field-help", text: "Public to all agents. Private details of the simulated human belong in the Human Persona." })
    ),
    h(
      "div",
      { class: "field" },
      h("label", { class: "field-label", for: "exp-initial", text: "Initial Message" }),
      initial,
      h("div", { class: "field-help", text: `Sent by ${humanName} as the first turn of round 1.` }),
      initialError
    )
  );

  const saveBtn = h("button", { class: "btn btn-primary", type: "button" }, icon("check"), "Save");
  const cancelBtn = h("button", { class: "btn", type: "button" }, "Cancel");
  const overlay = openOverlay({ title: "Scenario", body, footer: [cancelBtn, saveBtn] });

  cancelBtn.addEventListener("click", () => overlay.close("cancel"));
  saveBtn.addEventListener("click", () => {
    const message = initial.value.trim();
    initialError.hidden = Boolean(message);
    initialError.textContent = message ? "" : "The Initial Message cannot be empty.";
    initial.classList.toggle("invalid", !message);
    if (!message) return;
    onSave({ scenario: scenario.value.trim(), initialMessage: message });
    overlay.close("save");
  });
}
