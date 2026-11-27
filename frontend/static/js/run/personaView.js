// Read-only rendering of persona values, driven by the field definitions.

import { h } from "../core/dom.js";

export function displayValue(field, value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  return String(value);
}

/** Definition list of persona fields. `skip` lists field names to omit. */
export function personaList(fields, values, { skip = [], clampLong = false } = {}) {
  const rows = [];
  for (const field of fields) {
    if (skip.includes(field.name)) continue;
    const text = displayValue(field, values[field.name]);
    rows.push(
      h("dt", { text: field.label }),
      h("dd", { class: [text ? "" : "empty", clampLong && field.widget === "textarea" ? "clamp" : ""].join(" ").trim(), text: text ?? "Not specified" })
    );
  }
  return h("dl", { class: "kv" }, rows);
}

/** One-line summary of short fields, e.g. "Age 30 · Female · Japanese". */
export function personaOneLine(fields, values) {
  return fields
    .filter((field) => field.widget !== "textarea" && !["model", "name", "language"].includes(field.name))
    .map((field) => {
      const text = displayValue(field, values[field.name]);
      if (!text || text === "Unspecified") return null;
      return field.widget === "number" ? `${field.label} ${text}` : text;
    })
    .filter(Boolean)
    .join(" · ");
}
