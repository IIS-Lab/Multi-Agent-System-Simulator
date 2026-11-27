"""Scores a finished transcript with the rubric in backend/config/rubric.py.

One evaluator call per ROUND (run in parallel, at most EVALUATOR_CONCURRENCY at
a time). Each call sees the scenario, every participant's persona (including
the Human Agent's private context) and the transcript up to that round, and
returns integer ratings for the round as a whole, for each AI participant (with
a short evidence note) and for the simulated human. Rating rounds separately
keeps the evaluator from copying one set of numbers across the whole run.
Normalization and the discounted aggregate are in scoring.py.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from backend.config import rubric
from backend.evaluation.scoring import aggregate, aggregate_human
from backend.openrouter.client import LLMClient, LLMError, complete_with_retries
from backend.persona.fields import persona_to_prompt_text
from backend.simulation.types import HumanAgentConfig, RunConfiguration, TranscriptEntry


def rubric_snapshot() -> dict[str, Any]:
    return {
        "unit": "round",
        "criteria": rubric.CRITERIA,
        "human_criteria": rubric.HUMAN_CRITERIA,
        "rating_scale": [rubric.SCALE_MIN, rubric.SCALE_MAX],
        "normalized_to": [0, 1],
        "discount": rubric.DISCOUNT,
        "formula": "overall = sum_t w_t * turn_score_t / sum_t w_t, w_t = discount^(t-1), turn = round",
        "method": "one evaluator call per round, seeing the transcript up to that round",
        "breakdown": "the same discounted average per criterion, per agent and per agent x criterion",
        "human_check": "the simulated human is rated separately with human_criteria and is not part of overall",
    }


def _participants_text(config: RunConfiguration) -> str:
    blocks = []
    for agent in config.all_agents():
        kind = "simulated human participant" if agent.agent_type == "human_simulation" else "AI participant"
        lines = [f"{agent.name} ({kind}):", persona_to_prompt_text(agent.persona_agent)]
        if isinstance(agent, HumanAgentConfig):
            lines += ["Private context (not known to the others):", persona_to_prompt_text(agent.persona_human)]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _parse(text: str) -> dict[str, Any]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("The evaluator did not return a JSON object.")
    return json.loads(match.group(0))


def _criteria_text(criteria: list[dict[str, Any]]) -> str:
    lines = []
    for c in criteria:
        lines.append(f"- {c['key']}: {c['description']}")
        for level, text in sorted((c.get("levels") or {}).items()):
            lines.append(f"    {level} = {text}")
    return "\n".join(lines)


def _valid_rating(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if rubric.SCALE_MIN <= value <= rubric.SCALE_MAX else None


def _add_usage(total: dict[str, Any], usage: dict[str, Any] | None) -> None:
    for key, value in (usage or {}).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value


async def evaluate_transcript(
    llm: LLMClient, config: RunConfiguration, transcript: list[TranscriptEntry]
) -> dict[str, Any]:
    """Return the "evaluation" section of a result document. Never raises."""
    base = {"version": 3, "rubric": rubric_snapshot(), "evaluator_model": rubric.EVALUATOR_MODEL}
    ai_agents = list(config.agents)
    # A round is scored when at least one AI participant replied in it.
    rounds = sorted({t.round for t in transcript if t.agent_type == "ai_agent" and t.source == "generated"})
    if not rounds:
        return {**base, "status": "skipped", "error": "No rounds with AI replies to score.", "scores": None, "turns": []}

    keys = [c["key"] for c in rubric.CRITERIA]
    human_keys = [c["key"] for c in rubric.HUMAN_CRITERIA]
    # The Human Agent's first message is a fixed script, so only generated messages are rated.
    human_rounds = {t.round for t in transcript if t.agent_type == "human_simulation" and t.source == "generated"}
    participants = _participants_text(config)
    semaphore = asyncio.Semaphore(max(1, rubric.EVALUATOR_CONCURRENCY))

    async def rate_round(number: int) -> tuple[dict[str, Any] | None, Any, str | None]:
        rate_human = number in human_rounds
        prompt = rubric.USER_PROMPT.format(
            round=number,
            scenario=config.scenario.strip() or "(none)",
            participants=participants,
            transcript="\n".join(
                f"#{t.sequence} [round {t.round}] {t.agent_name}: {t.content}" for t in transcript if t.round <= number
            ),
            scale_min=rubric.SCALE_MIN,
            scale_max=rubric.SCALE_MAX,
            criteria=_criteria_text(rubric.CRITERIA),
            human_criteria=_criteria_text(rubric.HUMAN_CRITERIA),
            human_name=config.human_agent.name,
            human_instruction=(
                f"ratings for {config.human_agent.name}'s message in round {number}, with \"evidence\": one short sentence quoting or pointing to the words that justify them;"
                if rate_human
                else f"null ({config.human_agent.name}'s message in this round is a fixed script and is not rated);"
            ),
            human_shape=("{" + ", ".join(f'"{k}": <int>' for k in human_keys) + ', "evidence": "<text>"}') if rate_human else "null",
            score_keys=", ".join(f'"{k}": <int>' for k in keys),
            criteria_keys=", ".join(keys),
            human_criteria_keys=", ".join(human_keys),
            rate_human="yes" if rate_human else "no",
            agent_names=", ".join(agent.name for agent in ai_agents),
        )
        async with semaphore:
            try:
                completion = await complete_with_retries(
                    llm,
                    model=rubric.EVALUATOR_MODEL,
                    messages=[{"role": "system", "content": rubric.SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=max(4000, 1500 + 250 * len(ai_agents)),
                    timeout=300,
                    max_attempts=2,
                    reasoning_effort=rubric.EVALUATOR_REASONING_EFFORT,
                    json_output=True,
                )
                raw = _parse(completion.content)
            except (LLMError, ValueError) as exc:
                return None, None, exc.message if isinstance(exc, LLMError) else str(exc)
        return (raw if isinstance(raw, dict) else {}), completion, None

    outcomes = await asyncio.gather(*(rate_round(number) for number in rounds))

    usage: dict[str, Any] = {}
    cost = 0.0
    errors = []
    rated = []
    for number, (item, completion, error) in zip(rounds, outcomes):
        if error:
            errors.append(f"round {number}: {error}")
        if completion is not None:
            _add_usage(usage, completion.usage)
            cost += completion.cost or 0.0
        item = item or {}
        ratings = {key: _valid_rating((item.get("scores") or {}).get(key)) for key in keys}
        returned_agents = item.get("agents") if isinstance(item.get("agents"), dict) else {}
        agents = {}
        for agent in ai_agents:
            agent_ratings = returned_agents.get(agent.name) or {}
            if not isinstance(agent_ratings, dict):
                agent_ratings = {}
            agents[agent.id] = {
                "agent_name": agent.name,
                "ratings": {key: _valid_rating(agent_ratings.get(key)) for key in keys},
                "evidence": str(agent_ratings.get("evidence") or "")[:500],
            }
        human = None
        if number in human_rounds:
            returned_human = item.get("human") if isinstance(item.get("human"), dict) else {}
            human = {key: _valid_rating(returned_human.get(key)) for key in human_keys}
        rated.append(
            {
                "round": number,
                "ratings": ratings,
                "agents": agents,
                "human": human,
                "human_evidence": str(((item.get("human") or {}) if isinstance(item.get("human"), dict) else {}).get("evidence") or "")[:500],
                "note": str(item.get("note", ""))[:1000],
            }
        )

    if len(errors) == len(rounds):
        return {**base, "status": "failed", "error": "; ".join(errors)[:2000], "scores": None, "turns": [], "usage": usage, "cost": cost}

    turns, scores = aggregate(rated, keys, discount=rubric.DISCOUNT, scale_min=rubric.SCALE_MIN, scale_max=rubric.SCALE_MAX)
    scores["human_agent"] = aggregate_human(
        turns, human_keys, agent_name=config.human_agent.name, discount=rubric.DISCOUNT, scale_min=rubric.SCALE_MIN, scale_max=rubric.SCALE_MAX
    )
    missing = sum(1 for t in turns if t["turn_score"] is None)
    problems = errors + ([f"{missing} round(s) were not rated by the evaluator."] if missing else [])
    return {
        **base,
        "status": "completed",
        "error": "; ".join(problems)[:2000] or None,
        "scores": scores,
        "turns": turns,
        "usage": usage,
        "cost": cost,
    }
