// Readable view of the `transcript` array of a result document.

import { h } from "../core/dom.js";
import { formatDateTime } from "../core/format.js";
import { icon } from "../core/icons.js";

export function renderTranscript(document_) {
  const transcript = Array.isArray(document_.transcript) ? document_.transcript : [];
  const view = h("div", { class: "transcript-view" });
  if (!transcript.length) {
    view.append(h("div", { class: "list-state" }, icon("message"), "This result has no transcript entries."));
    return view;
  }

  // Rubric ratings are per round (and per agent inside each round).
  const rated = new Map(((document_.evaluation && document_.evaluation.turns) || []).map((turn) => [turn.round, turn]));
  let currentRound = null;
  for (const entry of transcript) {
    if (entry.round !== currentRound) {
      currentRound = entry.round;
      const roundRating = rated.get(entry.round);
      view.append(
        h(
          "div",
          { class: "round-divider" },
          h("span", { text: `Round ${entry.round}` }),
          roundRating && typeof roundRating.turn_score === "number"
            ? h("span", { class: "score-chip", title: ratingTitle(roundRating), text: `Round score ${roundRating.turn_score.toFixed(2)}` })
            : null
        )
      );
    }
    const isHuman = entry.agent_type === "human_simulation";
    const meta = [entry.model, entry.source === "initial_message" ? "initial message" : null, formatDateTime(entry.timestamp)].filter(Boolean).join(" · ");
    view.append(
      h(
        "div",
        { class: `msg ${isHuman ? "human" : ""}` },
        h("span", { class: `avatar-icon ${isHuman ? "avatar-human" : "avatar-robot"}` }, icon(isHuman ? "person" : "robot")),
        h(
          "div",
          { class: "msg-body" },
          h(
            "div",
            { class: "msg-head" },
            h("span", { class: "who", text: entry.agent_name }),
            h("span", { class: "meta", text: `#${entry.sequence} · ${meta}` }),
            agentChip(rated.get(entry.round), entry.agent_id)
          ),
          h("div", { class: "msg-text", text: entry.content })
        )
      )
    );
  }
  return view;
}

function ratingTitle(rating) {
  const details = Object.entries(rating.ratings || {})
    .map(([key, value]) => `${key}: ${value ?? "—"}`)
    .join("\n");
  return `${details}${rating.note ? `\n\n${rating.note}` : ""}`;
}

function agentChip(roundRating, agentId) {
  const agent = roundRating && roundRating.agents && roundRating.agents[agentId];
  if (!agent || typeof agent.score !== "number") return null;
  return h("span", { class: "score-chip subtle", title: ratingTitle(agent), text: `${agent.score.toFixed(2)}` });
}
