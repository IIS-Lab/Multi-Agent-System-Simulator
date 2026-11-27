"""Speaking-order logic.

Every round the Human Agent speaks first, then each AI Agent speaks exactly once.
  sequential: AI Agents in their configured order (Agent 1, Agent 2, ...)
  randomized: a fresh random permutation of all AI Agents for each round
Randomization uses the run's `random_seed`, so a schedule can be reproduced.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from backend.simulation.types import Ordering, RunConfiguration


@dataclass(frozen=True)
class ScheduledTurn:
    round: int
    sequence: int
    position_in_round: int
    agent_id: str


def order_for_round(
    human_agent_id: str, ai_agent_ids: list[str], ordering: Ordering, rng: random.Random
) -> list[str]:
    ai_order = list(ai_agent_ids)
    if ordering == "randomized":
        rng.shuffle(ai_order)
    elif ordering != "sequential":
        raise ValueError(f"Unknown ordering: {ordering}")
    return [human_agent_id, *ai_order]


def build_schedule(config: RunConfiguration) -> list[ScheduledTurn]:
    """Return every speaking turn of the run, in order."""
    rng = random.Random(config.random_seed)
    ai_ids = [agent.id for agent in config.agents]
    schedule: list[ScheduledTurn] = []
    sequence = 0
    for round_number in range(1, config.rounds + 1):
        order = order_for_round(config.human_agent.id, ai_ids, config.ordering, rng)
        for position, agent_id in enumerate(order, start=1):
            sequence += 1
            schedule.append(ScheduledTurn(round_number, sequence, position, agent_id))
    return schedule
