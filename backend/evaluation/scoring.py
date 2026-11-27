"""Pure aggregation of rubric ratings (no model calls).

Unit = one ROUND (the Human Agent's message plus every AI Agent's reply in that
round), not a single message.

Input per round (from evaluator.py):
    {"round": t, "ratings": {criterion: int|None},            # the round as a whole
     "agents": {agent_id: {"agent_name": str, "ratings": {criterion: int|None}, "evidence": str}},
     "human": {human criterion: int|None} | None, "human_evidence": str,
     "note": str}

Everything is normalized to 0..1:
    n(x)               = (x - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)
    turn_score[t]      = mean over criteria of n(round rating)
    w[t]               = DISCOUNT**(t-1) / sum_k DISCOUNT**(k-1)          (weights sum to 1)
    overall            = sum_t w[t] * turn_score[t]                          (0..1)

The same discounted average is computed per criterion, per agent (from the
agent's own ratings in each round) and per agent x criterion, so smaller
differences can be inspected.
"""

from __future__ import annotations

from statistics import mean
from typing import Any


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def round_weights(rounds: list[int], discount: float) -> dict[int, float]:
    raw = {r: discount ** (r - 1) for r in rounds}
    total = sum(raw.values())
    return {r: raw[r] / total for r in rounds}


def _discounted(values: dict[int, float | None], discount: float) -> float | None:
    present = {r: v for r, v in values.items() if v is not None}
    if not present:
        return None
    weights = round_weights(sorted(present), discount)
    return sum(weights[r] * present[r] for r in present)


def _human_detail(ratings, norm, evidence=""):
    """ratings: {human criterion: int|None} (keys come from HUMAN_CRITERIA), or None if not rated."""
    if ratings is None:
        return None
    normalized = {k: _r(norm(v)) for k, v in ratings.items()}
    return {
        "ratings": ratings,
        "normalized": normalized,
        "score": _r(_mean([v for v in normalized.values() if v is not None])),
        "evidence": evidence,
    }


def aggregate_human(
    turns: list[dict[str, Any]],
    criteria_keys: list[str],
    *,
    agent_name: str,
    discount: float,
    scale_min: float,
    scale_max: float,
) -> dict[str, Any]:
    """Discounted summary of the simulated human's ratings (rounds where it was rated)."""
    rated = [t for t in turns if t.get("human")]
    per_round = {t["round"]: t["human"]["score"] for t in rated}
    return {
        "agent_name": agent_name,
        "discounted": _r(_discounted(per_round, discount)),
        "mean": _r(_mean([v for v in per_round.values() if v is not None])),
        "by_round": {str(r): v for r, v in per_round.items()},
        "by_criterion": {
            key: {
                "discounted": _r(_discounted({t["round"]: t["human"]["normalized"].get(key) for t in rated}, discount)),
                "by_round": {str(t["round"]): t["human"]["normalized"].get(key) for t in rated},
            }
            for key in criteria_keys
        },
    }


def aggregate(
    rated: list[dict[str, Any]],
    criteria_keys: list[str],
    *,
    discount: float,
    scale_min: float,
    scale_max: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (turns, scores): per-round details and the aggregated "scores" section."""

    def norm(value):
        return None if value is None else (value - scale_min) / (scale_max - scale_min)

    def criteria_mean(ratings: dict[str, Any]) -> float | None:
        return _mean([norm(ratings[k]) for k in criteria_keys if ratings.get(k) is not None])

    turns = []
    for item in rated:
        agents = {}
        for agent_id, detail in (item.get("agents") or {}).items():
            ratings = detail.get("ratings") or {}
            agents[agent_id] = {
                "agent_name": detail.get("agent_name", agent_id),
                "ratings": ratings,
                "normalized": {k: _r(norm(ratings.get(k))) for k in criteria_keys},
                "score": _r(criteria_mean(ratings)),
                "evidence": detail.get("evidence", ""),
            }
        ratings = item.get("ratings") or {}
        turns.append(
            {
                "round": item["round"],
                "ratings": ratings,
                "normalized": {k: _r(norm(ratings.get(k))) for k in criteria_keys},
                "turn_score": _r(criteria_mean(ratings)),
                "agents": agents,
                "human": _human_detail(item.get("human"), norm, item.get("human_evidence", "")),
                "note": item.get("note", ""),
            }
        )

    scored_rounds = [t["round"] for t in turns if t["turn_score"] is not None]
    weights = round_weights(scored_rounds, discount) if scored_rounds else {}
    for turn in turns:
        turn["weight"] = _r(weights.get(turn["round"]))

    turn_scores = {t["round"]: t["turn_score"] for t in turns}

    by_criterion = {}
    for key in criteria_keys:
        per_round = {t["round"]: t["normalized"][key] for t in turns}
        by_criterion[key] = {
            "discounted": _r(_discounted(per_round, discount)),
            "mean": _r(_mean([v for v in per_round.values() if v is not None])),
            "by_round": {str(r): v for r, v in per_round.items()},
        }

    agent_ids = list(dict.fromkeys(a for t in turns for a in t["agents"]))
    by_agent = {}
    for agent_id in agent_ids:
        per_round = {t["round"]: t["agents"].get(agent_id, {}).get("score") for t in turns}
        name = next(t["agents"][agent_id]["agent_name"] for t in turns if agent_id in t["agents"])
        by_agent[agent_id] = {
            "agent_name": name,
            "discounted": _r(_discounted(per_round, discount)),
            "mean": _r(_mean([v for v in per_round.values() if v is not None])),
            "by_round": {str(r): v for r, v in per_round.items()},
            "by_criterion": {
                key: _r(
                    _discounted({t["round"]: t["agents"].get(agent_id, {}).get("normalized", {}).get(key) for t in turns}, discount)
                )
                for key in criteria_keys
            },
        }

    scores = {
        "unit": "round",
        "scale": "normalized 0..1 (0 = worst, 1 = best)",
        "discount": discount,
        "overall": {
            "discounted": _r(_discounted(turn_scores, discount)),
            "mean": _r(_mean([v for v in turn_scores.values() if v is not None])),
        },
        "round_weights": {str(r): _r(w) for r, w in weights.items()},
        "by_round": {str(t["round"]): t["turn_score"] for t in turns},
        "by_criterion": by_criterion,
        "by_agent": by_agent,
    }
    return turns, scores
