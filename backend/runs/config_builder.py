"""Turns the browser's experiment request into a frozen RunConfiguration.

Agent ids are assigned here by position (agent_1, agent_2, ...). Names come from
persona_agent.name, or default to "Human Agent" / "Agent N". Prompt templates and
generation parameters come from backend/config, so the snapshot records exactly
what the run will use.
"""

from __future__ import annotations

import secrets

from pydantic import BaseModel, ConfigDict, Field

from backend.config import prompts
from backend.config import simulation_defaults as defaults
from backend.config.initial_message import INITIAL_MESSAGE
from backend.config.scenario import DEFAULT_SCENARIO, MAX_INITIAL_MESSAGE_LENGTH, MAX_SCENARIO_LENGTH
from backend.persona.persona_agent import PersonaAgent
from backend.persona.persona_human import PersonaHuman
from backend.simulation.types import (
    AIAgentConfig,
    GenerationParams,
    HUMAN_AGENT_NAME,
    HumanAgentConfig,
    Ordering,
    PromptTemplates,
    RunConfiguration,
)


class HumanAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    persona_agent: PersonaAgent
    persona_human: PersonaHuman


class AIAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    persona_agent: PersonaAgent


class ExperimentRequest(BaseModel):
    """Payload sent by the Run Experiment page."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    label: str = Field("", max_length=100)
    rounds: int = Field(ge=1, le=defaults.MAX_ROUNDS, strict=True)
    ordering: Ordering
    scenario: str = Field(DEFAULT_SCENARIO, max_length=MAX_SCENARIO_LENGTH)
    initial_message: str = Field(INITIAL_MESSAGE, min_length=1, max_length=MAX_INITIAL_MESSAGE_LENGTH)
    human_agent: HumanAgentInput
    agents: list[AIAgentInput] = Field(min_length=1, max_length=defaults.MAX_AI_AGENTS)


class ConfigurationError(ValueError):
    pass


def build_run_configuration(request: ExperimentRequest, llm_provider: str) -> RunConfiguration:
    human_name = request.human_agent.persona_agent.name or HUMAN_AGENT_NAME
    agent_names = [agent.persona_agent.name or f"Agent {index}" for index, agent in enumerate(request.agents, start=1)]
    names = [human_name, *agent_names]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ConfigurationError(f"Agent names must be unique (duplicated: {', '.join(duplicates)}).")

    return RunConfiguration(
        label=request.label,
        rounds=request.rounds,
        ordering=request.ordering,
        random_seed=secrets.randbelow(2**31),
        scenario=request.scenario,
        initial_message=request.initial_message,
        llm_provider=llm_provider,
        human_agent=HumanAgentConfig(
            name=human_name,
            persona_agent=request.human_agent.persona_agent,
            persona_human=request.human_agent.persona_human,
        ),
        agents=[
            AIAgentConfig(id=f"agent_{index}", name=name, persona_agent=agent.persona_agent)
            for index, (name, agent) in enumerate(zip(agent_names, request.agents), start=1)
        ],
        generation=GenerationParams(),
        prompt_templates=PromptTemplates(
            human_agent_system_prompt=prompts.HUMAN_AGENT_SYSTEM_PROMPT,
            ai_agent_system_prompt=prompts.AI_AGENT_SYSTEM_PROMPT,
        ),
    )
