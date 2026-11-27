// Experiment draft state for the Run Experiment page.
//
// Persona fields are NOT hard-coded here: they come from the server
// (backend/persona/persona_agent.py and persona_human.py) via /api/experiment/schema.

const DRAFT_KEY = "mas.experimentDraft.v1";

let nextUid = 1;
export const newUid = () => `a${nextUid++}`;

export function defaultsFromFields(fields) {
  return Object.fromEntries(fields.map((field) => [field.name, field.default ?? ""]));
}

// Older configurations had a separate mental_wellbeing_context; it is folded into additional_context.
const LEGACY_HUMAN_FIELDS = ["mental_wellbeing_context"];

export function migratePersonaHuman(values) {
  if (!values || !LEGACY_HUMAN_FIELDS.some((key) => key in values)) return values;
  const parts = [...LEGACY_HUMAN_FIELDS.map((key) => values[key]), values.additional_context]
    .filter((text) => typeof text === "string" && text.trim())
    .map((text) => text.trim());
  const migrated = { ...values, additional_context: parts.join("\n\n") };
  LEGACY_HUMAN_FIELDS.forEach((key) => delete migrated[key]);
  return migrated;
}

/** Keep only currently defined fields; fill missing ones with defaults. */
export function normalizePersona(fields, values = {}) {
  const result = {};
  for (const field of fields) {
    let value = values && values[field.name] !== undefined ? values[field.name] : field.default;
    // Saved drafts may hold values that are no longer allowed (e.g. a removed model).
    if (field.options && !field.options.includes(value)) value = field.default;
    result[field.name] = value ?? "";
  }
  return result;
}

/**
 * Build a draft from a plain experiment object (saved draft, imported JSON, or a
 * result's configuration). Unknown persona fields are dropped; missing ones get defaults.
 */
export function draftFromExperiment(schema, raw = {}) {
  const agentFields = schema.persona_agent_fields;
  const humanFields = schema.persona_human_fields;
  const rawAgents = Array.isArray(raw.agents) && raw.agents.length ? raw.agents : [{}];
  const rounds = Number.isInteger(raw.rounds) && raw.rounds >= 1 && raw.rounds <= schema.max_rounds ? raw.rounds : schema.default_rounds;
  return {
    label: typeof raw.label === "string" ? raw.label : typeof raw.name === "string" ? raw.name : "",
    scenario: typeof raw.scenario === "string" ? raw.scenario : schema.default_scenario || "",
    initialMessage: typeof raw.initial_message === "string" && raw.initial_message.trim() ? raw.initial_message : schema.initial_message,
    rounds,
    roundsText: String(rounds),
    ordering: raw.ordering === "randomized" ? "randomized" : "sequential",
    human: {
      persona_agent: normalizePersona(agentFields, raw.human_agent?.persona_agent),
      persona_human: normalizePersona(humanFields, migratePersonaHuman(raw.human_agent?.persona_human)),
    },
    agents: rawAgents
      .slice(0, schema.max_ai_agents)
      .map((agent) => ({ uid: newUid(), persona_agent: normalizePersona(agentFields, agent?.persona_agent) })),
  };
}

export function createDraft(schema) {
  return draftFromExperiment(schema, loadSavedDraft() || {});
}

/** Experiment object in the import/export JSON format (also what saveDraft stores). */
export function experimentFromDraft(draft) {
  return {
    label: draft.label,
    rounds: draft.rounds,
    ordering: draft.ordering,
    scenario: draft.scenario,
    initial_message: draft.initialMessage,
    human_agent: { persona_agent: draft.human.persona_agent, persona_human: draft.human.persona_human },
    agents: draft.agents.map((agent) => ({ persona_agent: agent.persona_agent })),
  };
}

export const humanDisplayName = (draft) => draft.human.persona_agent.name || "Human Agent";
export const agentDisplayName = (agent, index) => agent.persona_agent.name || `Agent ${index + 1}`;

export function newAgent(schema) {
  return { uid: newUid(), persona_agent: defaultsFromFields(schema.persona_agent_fields) };
}

/** Validate the rounds input text. Returns { value, error }. */
export function parseRounds(text, maxRounds) {
  const trimmed = String(text).trim();
  if (!/^\d+$/.test(trimmed)) return { value: null, error: "Rounds must be a positive whole number." };
  const value = Number(trimmed);
  if (value < 1) return { value: null, error: "Rounds must be at least 1." };
  if (value > maxRounds) return { value: null, error: `Rounds cannot exceed ${maxRounds}.` };
  return { value, error: null };
}

/** The request body for POST /api/runs/prepare. */
export const toExperimentRequest = (draft) => experimentFromDraft(draft);

export function saveDraft(draft) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(experimentFromDraft(draft)));
  } catch {
    /* storage unavailable: the draft simply is not remembered */
  }
}

function loadSavedDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
    // Drafts saved by older versions stored the Human Agent under "human".
    if (saved && saved.human && !saved.human_agent) saved.human_agent = saved.human;
    return saved;
  } catch {
    return null;
  }
}

/** Minimal observable store. */
export function createStore(initial) {
  let state = initial;
  const listeners = new Set();
  return {
    get: () => state,
    update(patch) {
      state = { ...state, ...(typeof patch === "function" ? patch(state) : patch) };
      listeners.forEach((listener) => listener(state));
    },
    subscribe(listener) {
      listeners.add(listener);
      listener(state);
    },
  };
}

/** Phases: idle | confirming | running | stopping | completed | stopped | failed */
export const isBusy = (phase) => phase === "confirming" || phase === "running" || phase === "stopping";
