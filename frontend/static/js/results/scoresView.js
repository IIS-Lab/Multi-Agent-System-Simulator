// Rubric scores of a result: overall score plus round / agent / criterion breakdowns.
// All values are normalized to 0..1. Cells are shaded with one hue (darker = higher)
// and always show the number, so the color is never the only cue.

import { h } from "../core/dom.js";
import { icon } from "../core/icons.js";

const criterionTitle = (criterion) =>
  [criterion.description, ...Object.entries(criterion.levels || {}).map(([level, text]) => `${level} = ${text}`)].join("\n");

const fmt = (value) => (typeof value === "number" ? value.toFixed(2) : "—");

function cell(value, title) {
  const shaded = typeof value === "number";
  return h(
    "td",
    {
      class: `heat ${shaded ? "" : "empty"}`,
      title: title || undefined,
      style: shaded ? { "--heat": `${Math.round(6 + value * 54)}%` } : undefined,
    },
    fmt(value)
  );
}

function heatTable({ caption, columns, rows }) {
  return h(
    "div",
    { class: "score-block" },
    h("h3", { text: caption }),
    h(
      "div",
      { class: "heat-wrap" },
      h(
        "table",
        { class: "heat-table" },
        h("thead", null, h("tr", null, h("th", { text: "" }), columns.map((col) => h("th", null, col.label, col.sub ? h("span", { class: "sub", text: col.sub }) : null)))),
        h(
          "tbody",
          null,
          rows.map((row) => h("tr", { class: row.emphasis ? "emphasis" : "" }, h("th", { scope: "row", text: row.label }), row.cells))
        )
      )
    )
  );
}

export function renderScores(doc) {
  const evaluation = doc.evaluation;
  const view = h("div", { class: "scores-view" });
  if (!evaluation) {
    view.append(h("div", { class: "list-state" }, icon("list"), "This result has no rubric evaluation."));
    return view;
  }
  if (evaluation.status !== "completed" || !evaluation.scores) {
    view.append(
      h("div", { class: "list-state" }, h("div", { class: "alert alert-warning" }, icon("alert"), h("span", { text: `Evaluation ${evaluation.status || "unavailable"}. ${evaluation.error || ""}` })))
    );
    return view;
  }
  if (!evaluation.scores.overall) {
    view.append(h("div", { class: "list-state" }, "This result uses an older score format. See the JSON tab."));
    return view;
  }

  const scores = evaluation.scores;
  const turns = evaluation.turns || [];
  const rounds = turns.map((turn) => turn.round);
  const criteria = (evaluation.rubric && evaluation.rubric.criteria) || [];
  const agents = Object.entries(scores.by_agent || {});
  const roundColumns = rounds.map((r) => ({ label: `Round ${r}`, sub: `w ${fmt(scores.round_weights[String(r)])}` }));
  const summaryColumns = [{ label: "Discounted" }, { label: "Mean" }];

  // ---- Summary cards ----
  view.append(
    h(
      "div",
      { class: "score-cards" },
      h("div", { class: "score-card primary" }, h("div", { class: "label", text: "Overall (discounted)" }), h("div", { class: "value", text: fmt(scores.overall.discounted) })),
      h("div", { class: "score-card" }, h("div", { class: "label", text: "Mean of rounds" }), h("div", { class: "value", text: fmt(scores.overall.mean) })),
      scores.human_agent
        ? h(
            "div",
            { class: "score-card", title: "How human-like the simulated human was. A check on the simulator; not part of Overall." },
            h("div", { class: "label", text: "Simulated human check" }),
            h("div", { class: "value", text: fmt(scores.human_agent.discounted) })
          )
        : null,
      h("div", { class: "score-card" }, h("div", { class: "label", text: "Discount γ" }), h("div", { class: "value", text: String(scores.discount) })),
      h("div", { class: "score-card" }, h("div", { class: "label", text: "Rounds rated" }), h("div", { class: "value", text: String(rounds.length) })),
      h("div", { class: "score-card" }, h("div", { class: "label", text: "Evaluator" }), h("div", { class: "value mono small", text: evaluation.evaluator_model || "—" }))
    ),
    h(
      "p",
      { class: "field-help formula" },
      "Unit = one round. Ratings (1–5) are normalized to 0–1. Round score = mean over criteria. Overall = Σ wₜ · round scoreₜ with wₜ = γ^(t−1) / Σ γ^(k−1), so the weights sum to 1."
    )
  );

  // ---- Rounds x (group + agents) ----
  view.append(
    heatTable({
      caption: "By round",
      columns: [...roundColumns, ...summaryColumns],
      rows: [
        {
          label: "Round (all agents)",
          emphasis: true,
          cells: [
            ...turns.map((turn) => cell(turn.turn_score, turn.note)),
            cell(scores.overall.discounted),
            cell(scores.overall.mean),
          ],
        },
        ...agents.map(([agentId, agent]) => ({
          label: agent.agent_name,
          cells: [
            ...rounds.map((r) => {
              const detail = turns.find((turn) => turn.round === r)?.agents?.[agentId];
              const title = detail
                ? [...Object.entries(detail.ratings || {}).map(([k, v]) => `${k}: ${v ?? "—"}`), detail.evidence ? `\n${detail.evidence}` : ""].join("\n").trim()
                : "";
              return cell(agent.by_round[String(r)], title);
            }),
            cell(agent.discounted),
            cell(agent.mean),
          ],
        })),
      ],
    })
  );

  // ---- Criteria x rounds ----
  view.append(
    heatTable({
      caption: "By criterion (round as a whole)",
      columns: [...roundColumns, ...summaryColumns],
      rows: criteria.map((criterion) => {
        const stats = scores.by_criterion[criterion.key] || {};
        return {
          label: criterion.key,
          cells: [...rounds.map((r) => cell((stats.by_round || {})[String(r)], criterionTitle(criterion))), cell(stats.discounted), cell(stats.mean)],
        };
      }),
    })
  );

  // ---- Agents x criteria ----
  if (agents.length) {
    view.append(
      heatTable({
        caption: "By agent and criterion (discounted)",
        columns: criteria.map((criterion) => ({ label: criterion.key })),
        rows: agents.map(([, agent]) => ({
          label: agent.agent_name,
          cells: criteria.map((criterion) => cell((agent.by_criterion || {})[criterion.key], criterionTitle(criterion))),
        })),
      })
    );
  }

  // ---- Simulated human (simulator check) ----
  const human = scores.human_agent;
  const humanCriteria = (evaluation.rubric && evaluation.rubric.human_criteria) || [];
  if (human && Object.keys(human.by_round || {}).length) {
    const humanRounds = Object.keys(human.by_round);
    view.append(
      heatTable({
        caption: `Simulated human: ${human.agent_name} (simulator check, not in Overall)`,
        columns: [...humanRounds.map((r) => ({ label: `Round ${r}` })), { label: "Discounted" }],
        rows: [
          {
            label: "Score",
            emphasis: true,
            cells: [...humanRounds.map((r) => cell(human.by_round[r], turns.find((turn) => String(turn.round) === r)?.human?.evidence)), cell(human.discounted)],
          },
          ...humanCriteria.map((criterion) => {
            const stats = (human.by_criterion || {})[criterion.key] || {};
            return {
              label: criterion.key,
              cells: [...humanRounds.map((r) => cell((stats.by_round || {})[r], criterionTitle(criterion))), cell(stats.discounted)],
            };
          }),
        ],
      })
    );
  }

  // ---- Notes and evidence ----
  const explained = turns.filter((turn) => turn.note || turn.human?.evidence || Object.values(turn.agents || {}).some((a) => a.evidence));
  if (explained.length) {
    view.append(
      h(
        "div",
        { class: "score-block" },
        h("h3", { text: "Evaluator notes and evidence" }),
        explained.map((turn) =>
          h(
            "details",
            { class: "evidence", open: turn === explained[0] },
            h("summary", null, h("strong", { text: `Round ${turn.round}` }), turn.note ? h("span", { class: "muted", text: ` · ${turn.note}` }) : null),
            h(
              "dl",
              { class: "kv" },
              turn.human?.evidence ? [h("dt", { text: human ? human.agent_name : "Human" }), h("dd", { text: turn.human.evidence })] : null,
              Object.values(turn.agents || {})
                .filter((a) => a.evidence)
                .map((a) => [h("dt", { text: a.agent_name }), h("dd", { text: a.evidence })])
            )
          )
        )
      )
    );
  }

  view.append(
    h(
      "div",
      { class: "heat-legend" },
      h("span", { text: "0" }),
      h("span", { class: "ramp", "aria-hidden": "true" }),
      h("span", { text: "1" }),
      h("span", { class: "muted", text: "Darker = higher. Hover a cell for the raw ratings or notes." })
    )
  );
  return view;
}
