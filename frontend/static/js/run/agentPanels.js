// Top-left Human Agent panel and top-right AI Agents panel.

import { h } from "../core/dom.js";
import { icon } from "../core/icons.js";
import { agentDisplayName, humanDisplayName, isBusy } from "./experimentState.js";
import { personaList, personaOneLine } from "./personaView.js";

export function renderHumanPanel(body, state, { onEdit }) {
  const { schema, draft, phase } = state;
  const locked = isBusy(phase);
  const persona = draft.human.persona_agent;
  const name = humanDisplayName(draft);

  body.replaceChildren(
    h(
      "button",
      { class: "human-card", type: "button", disabled: locked, onclick: onEdit, "aria-label": "Edit Human Agent persona" },
      h(
        "div",
        { class: "agent-identity" },
        h("span", { class: "avatar-icon avatar-human lg" }, icon("person")),
        h(
          "div",
          { style: { minWidth: "0" } },
          h("div", { class: "agent-name", text: name }),
          h("div", { class: "agent-tag", text: persona.name ? "Human Agent · simulated human" : "Simulated human · LLM-driven" })
        )
      ),
      h("span", { class: "model-pill", title: persona.model, text: persona.model || "No model" }),
      h(
        "div",
        null,
        h("div", { class: "section-label", text: "Agent Persona" }),
        personaList(schema.persona_agent_fields, persona, { skip: ["model", "name"], clampLong: true })
      ),
      h(
        "div",
        null,
        h("div", { class: "section-label", text: "Human Persona" }),
        personaList(schema.persona_human_fields, draft.human.persona_human, { clampLong: true })
      ),
      h("span", { class: "card-cta" }, icon(locked ? "stop" : "edit"), locked ? "Locked while the experiment runs" : "Click to edit persona")
    )
  );
}

export function renderAgentsPanel(body, countEl, addBtn, state, { onEdit, onAdd, onRemove }) {
  const { schema, draft, phase } = state;
  const locked = isBusy(phase);
  const atMax = draft.agents.length >= schema.max_ai_agents;

  countEl.textContent = `${draft.agents.length} / ${schema.max_ai_agents}`;
  addBtn.disabled = locked || atMax;
  addBtn.title = atMax ? `Maximum of ${schema.max_ai_agents} AI Agents` : "Add AI Agent";

  const cards = draft.agents.map((agent, index) => {
    const name = agentDisplayName(agent, index);
    const persona = agent.persona_agent;
    const blurb = String(persona.profile || persona.ethics || "").trim();
    return h(
      "div",
      {
        class: `agent-card ${locked ? "locked" : ""}`,
        role: "button",
        tabindex: locked ? "-1" : "0",
        "aria-label": `Edit ${name} persona`,
        "aria-disabled": locked ? "true" : "false",
        onclick: () => !locked && onEdit(index),
        onkeydown: (event) => {
          if (!locked && (event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            onEdit(index);
          }
        },
      },
      h(
        "div",
        { class: "agent-identity" },
        h("span", { class: "avatar-icon avatar-robot" }, icon("robot")),
        h(
          "div",
          { style: { minWidth: "0" } },
          h("div", { class: "agent-name", text: name }),
          h("div", { class: "agent-tag", text: persona.name ? `Agent ${index + 1} · AI Agent` : "AI Agent" })
        )
      ),
      h("span", { class: "model-pill", title: persona.model, text: persona.model || "No model" }),
      h("div", { class: "agent-meta", text: personaOneLine(schema.persona_agent_fields, persona) || "No persona details" }),
      blurb ? h("div", { class: "agent-ethics clamp-2", text: blurb }) : null,
      h(
        "button",
        {
          class: "icon-btn remove-btn",
          type: "button",
          title: draft.agents.length <= 1 ? "At least one AI Agent is required" : `Remove ${name}`,
          "aria-label": `Remove ${name}`,
          disabled: locked || draft.agents.length <= 1,
          onclick: (event) => {
            event.stopPropagation();
            onRemove(index);
          },
        },
        icon("trash")
      )
    );
  });

  const addTile = atMax
    ? null
    : h(
        "button",
        { class: "add-tile", type: "button", disabled: locked, onclick: onAdd },
        h("span", { class: "plus-circle" }, icon("plus")),
        "Add Agent"
      );

  body.replaceChildren(h("div", { class: "agent-grid" }, cards, addTile));
}
