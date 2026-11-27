// Run Experiment page entry point: builds the four-area layout and wires modules together.

import { api } from "../core/api.js";
import { h } from "../core/dom.js";
import { mountHeader } from "../core/header.js";
import { icon } from "../core/icons.js";
import { toast } from "../core/overlay.js";
import { renderAgentsPanel, renderHumanPanel } from "./agentPanels.js";
import { agentDisplayName, createDraft, createStore, humanDisplayName, isBusy, newAgent, saveDraft } from "./experimentState.js";
import { exportDraft, parseImport, pickJsonFile } from "./importExport.js";
import { openPersonaEditor } from "./personaEditor.js";
import { mountProgressPanel } from "./progressPanel.js";
import { createRunController } from "./runController.js";
import { mountRunSettings } from "./runSettings.js";
import { openScenarioEditor } from "./scenarioEditor.js";

function panel(areaClass, titleChildren, actions = null) {
  const body = h("div", { class: "panel-body" });
  const element = h(
    "section",
    { class: `panel ${areaClass}` },
    h("div", { class: "panel-head" }, h("div", { class: "panel-title" }, titleChildren), actions),
    body
  );
  return { element, body };
}

async function init() {
  await mountHeader({ crumb: "Run Experiment" });
  const app = document.getElementById("app");

  let schema;
  try {
    schema = await api("/api/experiment/schema");
  } catch (error) {
    app.append(h("div", { class: "alert alert-danger" }, icon("alert"), h("span", { text: `Failed to load the experiment configuration. ${error.message}` })));
    return;
  }

  const store = createStore({ schema, draft: createDraft(schema), phase: "idle", run: null, batch: null, snapshot: null });
  const updateDraft = (change) => {
    store.update((state) => ({ draft: change(state.draft) }));
    saveDraft(store.get().draft);
  };

  // ---- Layout ----
  const human = panel("area-human", "Human Agent");
  const agentCount = h("span", { class: "count-pill" });
  const addBtn = h("button", { class: "btn btn-sm", type: "button", "aria-label": "Add AI Agent" }, icon("plus"), "Add");
  const agents = panel("area-agents", ["AI Agents", agentCount], addBtn);
  const scenarioBtn = h("button", { class: "btn btn-sm", type: "button", title: "Edit label, scenario and initial message" }, icon("message"), "Scenario");
  const importBtn = h("button", { class: "btn btn-sm btn-ghost", type: "button", title: "Import experiment JSON (one experiment or a batch)" }, icon("upload"), "Import");
  const exportBtn = h("button", { class: "btn btn-sm btn-ghost", type: "button", title: "Download the current configuration as JSON" }, icon("download"), "Export");
  const settings = panel("area-settings", "Rounds / Ordering", h("div", { class: "panel-actions" }, scenarioBtn, importBtn, exportBtn));
  const progressBadge = h("span");
  const progress = panel("area-progress", "Progress", progressBadge);
  app.append(h("div", { class: "run-grid" }, human.element, agents.element, settings.element, progress.element));

  // ---- Agents ----
  const editHuman = () => {
    const { draft } = store.get();
    openPersonaEditor({
      kind: "human",
      name: humanDisplayName(draft),
      schema,
      scenario: draft.scenario,
      value: draft.human,
      onSave: (saved) => updateDraft((d) => ({ ...d, human: { persona_agent: saved.persona_agent, persona_human: saved.persona_human } })),
    });
  };

  const editAgent = (index) => {
    const { draft } = store.get();
    const agent = draft.agents[index];
    openPersonaEditor({
      kind: "ai",
      name: agentDisplayName(agent, index),
      schema,
      scenario: draft.scenario,
      value: { persona_agent: agent.persona_agent },
      onSave: (saved) =>
        updateDraft((d) => ({ ...d, agents: d.agents.map((a, i) => (i === index ? { ...a, persona_agent: saved.persona_agent } : a)) })),
    });
  };

  const addAgent = () => {
    if (store.get().draft.agents.length >= schema.max_ai_agents) {
      toast(`You can add at most ${schema.max_ai_agents} AI Agents.`);
      return;
    }
    updateDraft((d) => ({ ...d, agents: [...d.agents, newAgent(schema)] }));
    requestAnimationFrame(() => (agents.body.scrollTop = agents.body.scrollHeight));
  };

  const removeAgent = (index) => updateDraft((d) => (d.agents.length <= 1 ? d : { ...d, agents: d.agents.filter((_, i) => i !== index) }));

  addBtn.addEventListener("click", addAgent);

  store.subscribe((state) => {
    renderHumanPanel(human.body, state, { onEdit: editHuman });
    renderAgentsPanel(agents.body, agentCount, addBtn, state, { onEdit: editAgent, onAdd: addAgent, onRemove: removeAgent });
  });

  // ---- Rounds / Ordering / Scenario / Import / Export ----
  mountRunSettings(settings.body, store, { onChange: updateDraft });
  const controller = createRunController(store);

  scenarioBtn.addEventListener("click", () => {
    const { draft } = store.get();
    openScenarioEditor({
      schema,
      draft,
      humanName: humanDisplayName(draft),
      onSave: (values) => updateDraft((d) => ({ ...d, ...values })),
    });
  });

  importBtn.addEventListener("click", async () => {
    const text = await pickJsonFile();
    if (text === null) return;
    let experiments;
    try {
      experiments = parseImport(text, schema);
    } catch (error) {
      toast(error.message);
      return;
    }
    const totalRuns = experiments.reduce((sum, item) => sum + item.repeats, 0);
    if (totalRuns === 1) {
      const draft = experiments[0].draft;
      updateDraft(() => draft);
      settings.body.querySelector("#rounds").value = draft.roundsText;
      toast(`Loaded ${draft.label || "the experiment"} into the editor. Press Start to run it.`, { kind: "success", timeout: 4000 });
    } else {
      controller.startBatch(experiments);
    }
  });

  exportBtn.addEventListener("click", () => exportDraft(store.get().draft));

  store.subscribe((state) => {
    const locked = isBusy(state.phase);
    scenarioBtn.disabled = locked;
    importBtn.disabled = locked;
    scenarioBtn.classList.toggle("has-value", Boolean(state.draft.scenario));
  });

  // ---- Progress / Start / Stop ----
  mountProgressPanel(progress.body, progressBadge, store, { onStart: controller.start, onStop: controller.stop });

  await controller.resumeIfActive();
}

init();
