"""Core data types for the simulation engine.

HumanAgent = PersonaAgent + PersonaHuman
AIAgent    = PersonaAgent
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.config import simulation_defaults as defaults
from backend.persona.persona_agent import PersonaAgent
from backend.persona.persona_human import PersonaHuman

Ordering = Literal["sequential", "randomized"]
AgentType = Literal["human_simulation", "ai_agent"]
SimulationStatus = Literal["completed", "stopped", "failed"]

HUMAN_AGENT_ID = "human_agent"
HUMAN_AGENT_NAME = "Human Agent"


class HumanAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = HUMAN_AGENT_ID
    name: str = HUMAN_AGENT_NAME
    agent_type: AgentType = "human_simulation"
    persona_agent: PersonaAgent
    persona_human: PersonaHuman


class AIAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    agent_type: AgentType = "ai_agent"
    persona_agent: PersonaAgent


class GenerationParams(BaseModel):
    temperature: float = defaults.TEMPERATURE
    max_tokens: int = defaults.MAX_TOKENS
    reasoning_effort: str | None = defaults.REASONING_EFFORT
    request_timeout_seconds: float = defaults.REQUEST_TIMEOUT_SECONDS
    max_attempts_per_turn: int = defaults.MAX_ATTEMPTS_PER_TURN


class PromptTemplates(BaseModel):
    human_agent_system_prompt: str
    ai_agent_system_prompt: str


class RunConfiguration(BaseModel):
    """Everything the engine needs to run one experiment. Frozen before a run starts."""

    label: str = ""  # optional experiment name, e.g. "young_voices"
    rounds: int = Field(ge=1, le=defaults.MAX_ROUNDS)
    ordering: Ordering
    random_seed: int
    scenario: str = ""
    initial_message: str
    llm_provider: str
    human_agent: HumanAgentConfig
    agents: list[AIAgentConfig] = Field(min_length=1, max_length=defaults.MAX_AI_AGENTS)
    generation: GenerationParams = Field(default_factory=GenerationParams)
    prompt_templates: PromptTemplates

    @property
    def total_turns(self) -> int:
        return self.rounds * (1 + len(self.agents))

    def all_agents(self) -> list[HumanAgentConfig | AIAgentConfig]:
        return [self.human_agent, *self.agents]


class TranscriptEntry(BaseModel):
    round: int
    sequence: int  # 1-based position across the whole run
    position_in_round: int  # 1-based position inside the round
    agent_id: str
    agent_name: str
    agent_type: AgentType
    model: str
    content: str
    timestamp: str
    source: Literal["initial_message", "generated"]
    # Request metadata (None for the hard-coded initial message).
    response_model: str | None = None  # model id reported by OpenRouter
    provider: str | None = None
    generation_id: str | None = None
    finish_reason: str | None = None
    latency_ms: int | None = None
    attempts: int | None = None
    usage: dict[str, Any] | None = None
    cost: float | None = None


class UsageTotals(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0

    def add(self, usage: dict[str, Any] | None, cost: float | None) -> None:
        usage = usage or {}
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)
        self.cost += float(cost or 0.0)


class SimulationError(BaseModel):
    kind: str
    message: str
    round: int | None = None
    sequence: int | None = None
    agent_id: str | None = None
    timestamp: str


class SimulationResult(BaseModel):
    """What `run_simulation` returns. Independent of UI and storage."""

    status: SimulationStatus
    stop_reason: str | None = None
    started_at: str
    completed_at: str
    total_turns: int
    completed_turns: int
    transcript: list[TranscriptEntry]
    usage: UsageTotals
    errors: list[SimulationError]
