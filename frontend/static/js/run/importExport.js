// Import / export of experiment configurations as JSON files.
//
// Accepted import formats:
//   1. One experiment:      { "label", "rounds", "ordering", "scenario", "initial_message",
//                             "human_agent": {...}, "agents": [...], "repeats"? }
//      (also wrapped as { "experiment": {...} })
//   2. Several experiments: { "experiments": [ <experiment>, ... ] }
//   3. A saved result file: { "configuration": {...} } — re-runs the same configuration.
// "repeats" (default 1) runs the same experiment several times. More than one run
// in total becomes a batch that runs one experiment after another.

import { downloadJson } from "../core/format.js";
import { draftFromExperiment, experimentFromDraft } from "./experimentState.js";

export const IMPORT_FORMAT = "mass-experiments";
export const IMPORT_VERSION = 1;

function pickExperiments(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.experiments)) return data.experiments;
  if (data && data.experiment && typeof data.experiment === "object") return [data.experiment];
  if (data && data.configuration && typeof data.configuration === "object") return [data.configuration];
  if (data && Array.isArray(data.agents)) return [data];
  throw new Error("Unrecognized file. Expected an experiment, an \"experiments\" list, or a saved result JSON.");
}

function checkExperiment(raw, position, schema) {
  const where = `Experiment ${position}`;
  if (!raw || typeof raw !== "object") throw new Error(`${where} is not an object.`);
  if (!Array.isArray(raw.agents) || raw.agents.length < 1) throw new Error(`${where} needs at least one agent in "agents".`);
  if (raw.agents.length > schema.max_ai_agents) throw new Error(`${where} has more than ${schema.max_ai_agents} agents.`);
  if (raw.rounds !== undefined && !(Number.isInteger(raw.rounds) && raw.rounds >= 1 && raw.rounds <= schema.max_rounds)) {
    throw new Error(`${where}: "rounds" must be a whole number from 1 to ${schema.max_rounds}.`);
  }
  if (raw.ordering !== undefined && !["sequential", "randomized"].includes(raw.ordering)) {
    throw new Error(`${where}: "ordering" must be "sequential" or "randomized".`);
  }
  const repeats = raw.repeats === undefined ? 1 : raw.repeats;
  if (!(Number.isInteger(repeats) && repeats >= 1 && repeats <= 50)) throw new Error(`${where}: "repeats" must be a whole number from 1 to 50.`);
  return repeats;
}

/** Parse imported JSON text into [{ draft, repeats }]. Throws Error with a readable message. */
export function parseImport(text, schema) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("The file is not valid JSON.");
  }
  const experiments = pickExperiments(data);
  if (!experiments.length) throw new Error("The file contains no experiments.");
  return experiments.map((raw, index) => {
    const repeats = checkExperiment(raw, index + 1, schema);
    return { draft: draftFromExperiment(schema, raw), repeats };
  });
}

/** Let the user pick a .json file; resolves with its text (or null if cancelled). */
export function pickJsonFile() {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json,.json";
    input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      resolve(file ? await file.text() : null);
    });
    input.click();
  });
}

export function exportDraft(draft) {
  const experiment = { ...experimentFromDraft(draft), repeats: 1 };
  const slug = (draft.label || "experiment").replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "experiment";
  downloadJson(`${slug}.json`, { format: IMPORT_FORMAT, version: IMPORT_VERSION, experiments: [experiment] });
}
