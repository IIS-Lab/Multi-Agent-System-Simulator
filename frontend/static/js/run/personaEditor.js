// Persona editor drawer. Edits a copy; changes apply only when Save is clicked.
// Form fields are generated from the server-provided field definitions.
// Fields marked `generatable` get a "Random" button that asks the server to
// generate text with the persona generator model and fills it in.

import { api } from "../core/api.js";
import { deepCopy, h } from "../core/dom.js";
import { icon } from "../core/icons.js";
import { openOverlay, toast } from "../core/overlay.js";

function buildInput(field, value, id) {
  const common = { id, name: field.name, placeholder: field.placeholder || "" };
  switch (field.widget) {
    case "textarea":
      return h("textarea", { ...common, class: "textarea", rows: 3, value: value ?? "" });
    case "number":
      return h("input", { ...common, class: "input", type: "number", inputmode: "numeric", step: "1", min: field.min ?? undefined, max: field.max ?? undefined, value: value ?? "" });
    case "select":
      return h(
        "select",
        { ...common, class: `select ${field.name === "model" ? "mono" : ""}` },
        (field.options || []).map((option) => h("option", { value: option, selected: option === value }, option))
      );
    case "combo": {
      // Text input with a suggestion list: choose from the list or type freely.
      const listId = `${id}-list`;
      return [
        h("input", { ...common, class: "input", type: "text", list: listId, autocomplete: "off", value: value ?? "" }),
        h("datalist", { id: listId }, (field.suggestions || []).map((option) => h("option", { value: option }))),
      ];
    }
    default:
      return h("input", { ...common, class: "input", type: "text", value: value ?? "" });
  }
}

function randomButton(title, onClick) {
  const button = h("button", { class: "btn btn-sm btn-ghost random-btn", type: "button", title }, icon("dice"), "Random");
  button.addEventListener("click", () => onClick(button));
  return button;
}

/** Show a spinner on a Random button while `task` runs. */
export async function withBusyButton(button, task) {
  const original = [...button.childNodes];
  button.disabled = true;
  button.replaceChildren(h("span", { class: "spinner" }), "Generating…");
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.replaceChildren(...original);
  }
}

/**
 * Build a form section for a list of fields. Returns { element, read, peek, setValues }.
 * onRandomField(fieldName, button) is called by per-field Random buttons.
 */
function buildFieldsForm(fields, values, prefix, { onRandomField = null } = {}) {
  const controls = [];
  const grid = h("div", { class: "form-grid" });

  for (const field of fields) {
    const id = `${prefix}-${field.name}`;
    const built = buildInput(field, values[field.name], id);
    const input = Array.isArray(built) ? built[0] : built;
    const error = h("div", { class: "field-error", hidden: true });
    const wide = field.widget === "textarea" || field.name === "model";
    const label = h("label", { class: "field-label", for: id, text: field.label });
    const labelRow =
      onRandomField && field.generatable
        ? h("div", { class: "field-label-row" }, label, randomButton(`Generate ${field.label}`, (button) => onRandomField(field.name, button)))
        : label;
    grid.append(
      h(
        "div",
        { class: `field ${wide ? "full" : ""}` },
        labelRow,
        built,
        field.help ? h("div", { class: "field-help", text: field.help }) : null,
        error
      )
    );
    controls.push({ field, input, error });
  }

  function read() {
    const result = {};
    let valid = true;
    for (const { field, input, error } of controls) {
      let value = input.value;
      let message = null;
      if (field.widget === "number") {
        const text = value.trim();
        if (!/^-?\d+$/.test(text)) message = `${field.label} must be a whole number.`;
        else {
          value = Number(text);
          if (field.min !== null && field.min !== undefined && value < field.min) message = `${field.label} must be at least ${field.min}.`;
          if (field.max !== null && field.max !== undefined && value > field.max) message = `${field.label} must be at most ${field.max}.`;
        }
      } else {
        value = value.trim();
      }
      error.hidden = !message;
      error.textContent = message || "";
      input.classList.toggle("invalid", Boolean(message));
      if (message) valid = false;
      result[field.name] = value;
    }
    return { valid, values: result };
  }

  /** Current values without showing validation errors (used as generation context). */
  function peek() {
    const result = {};
    for (const { field, input } of controls) {
      const text = input.value.trim();
      result[field.name] = field.widget === "number" && /^\d+$/.test(text) ? Number(text) : text;
    }
    return result;
  }

  function setValues(newValues) {
    for (const { field, input } of controls) {
      if (newValues[field.name] === undefined) continue;
      input.value = newValues[field.name];
      input.classList.remove("invalid");
      input.classList.remove("just-filled");
      void input.offsetWidth; // restart the highlight animation
      input.classList.add("just-filled");
    }
  }

  return { element: grid, read, peek, setValues };
}

/**
 * Open the editor.
 * kind "human": shows Agent Persona + Human Persona. kind "ai": Agent Persona only.
 * onSave receives { persona_agent, persona_human? }.
 */
export function openPersonaEditor({ kind, name, schema, value, scenario = "", onSave }) {
  const working = deepCopy(value);
  const generatorTitle = `Generate with ${schema.persona_generator_model}`;
  let busy = 0;

  async function generate(target, fieldNames, button) {
    busy += 1;
    saveBtn.disabled = true;
    try {
      await withBusyButton(button, async () => {
        const { values } = await api("/api/persona/generate", {
          method: "POST",
          body: { target, agent_kind: kind, fields: fieldNames, persona_agent: agentForm.peek(), scenario },
        });
        (target === "persona_agent" ? agentForm : humanForm).setValues(values);
      });
    } catch (error) {
      toast(error.message);
    } finally {
      busy -= 1;
      saveBtn.disabled = busy > 0;
    }
  }

  const agentForm = buildFieldsForm(schema.persona_agent_fields, working.persona_agent, "pa", {
    onRandomField: (fieldName, button) => generate("persona_agent", [fieldName], button),
  });
  const humanForm = kind === "human" ? buildFieldsForm(schema.persona_human_fields, working.persona_human, "ph") : null;
  const humanGeneratable = schema.persona_human_fields.filter((field) => field.generatable).map((field) => field.name);

  const body = h(
    "div",
    null,
    h(
      "div",
      { class: "editor-head-identity", style: { marginBottom: "24px" } },
      h("span", { class: `avatar-icon ${kind === "human" ? "avatar-human" : "avatar-robot"}` }, icon(kind === "human" ? "person" : "robot")),
      h(
        "div",
        null,
        h("div", { class: "agent-name", text: name }),
        h("div", { class: "agent-tag", text: kind === "human" ? "Simulated human · persona_agent + persona_human" : "AI Agent · persona_agent" })
      )
    ),
    h(
      "section",
      { class: "editor-section" },
      h("div", { class: "editor-section-title" }, icon("robot"), "Agent Persona", h("span", { class: "hint", text: "persona_agent" })),
      agentForm.element
    ),
    humanForm
      ? h(
          "section",
          { class: "editor-section" },
          h(
            "div",
            { class: "editor-section-title" },
            icon("person"),
            "Human Persona",
            h("span", { class: "hint", text: "persona_human" }),
            humanGeneratable.length
              ? randomButton(`${generatorTitle} (fills all Human Persona fields)`, (button) => generate("persona_human", humanGeneratable, button))
              : null
          ),
          humanForm.element
        )
      : null,
    h("p", { class: "field-help", style: { marginTop: "20px" }, text: `Random uses ${schema.persona_generator_model}. Review the text before saving.` })
  );

  const saveBtn = h("button", { class: "btn btn-primary", type: "button" }, icon("check"), "Save");
  const cancelBtn = h("button", { class: "btn", type: "button" }, "Cancel");

  const overlay = openOverlay({
    title: `Edit ${name}`,
    variant: "drawer",
    body,
    footer: [cancelBtn, saveBtn],
  });

  cancelBtn.addEventListener("click", () => overlay.close("cancel"));
  saveBtn.addEventListener("click", () => {
    const agentResult = agentForm.read();
    const humanResult = humanForm ? humanForm.read() : { valid: true };
    if (!agentResult.valid || !humanResult.valid) {
      const firstInvalid = overlay.root.querySelector(".invalid");
      if (firstInvalid) firstInvalid.focus();
      return;
    }
    const saved = { persona_agent: agentResult.values };
    if (humanForm) saved.persona_human = humanResult.values;
    onSave(saved);
    overlay.close("save");
  });
}
