"""Builds the chat messages sent to the model for one agent turn.

Conversation history is mapped from the speaker's point of view:
  the speaker's own earlier messages -> role "assistant"
  everyone else's messages            -> role "user", prefixed with "[Name]: "
Consecutive messages with the same role are merged, and the history always
starts with a "user" message, which keeps the format valid for all providers.
"""

from __future__ import annotations

from backend.config.prompts import EMPTY_SCENARIO
from backend.persona.fields import persona_to_prompt_text
from backend.simulation.types import (
    AIAgentConfig,
    HumanAgentConfig,
    RunConfiguration,
    TranscriptEntry,
)

CONVERSATION_START_NOTE = "[The conversation begins.]"


def build_system_prompt(
    agent: HumanAgentConfig | AIAgentConfig, config: RunConfiguration
) -> str:
    others = [a.name for a in config.all_agents() if a.id != agent.id]
    values = {
        "agent_name": agent.name,
        "scenario": config.scenario.strip() or EMPTY_SCENARIO,
        "persona_agent": persona_to_prompt_text(agent.persona_agent),
        "language": agent.persona_agent.language or "English",
        "participants": ", ".join(others),
    }
    if isinstance(agent, HumanAgentConfig):
        values["persona_human"] = persona_to_prompt_text(agent.persona_human)
        template = config.prompt_templates.human_agent_system_prompt
    else:
        template = config.prompt_templates.ai_agent_system_prompt
    return template.format(**values)


def build_messages(
    system_prompt: str, transcript: list[TranscriptEntry], speaker_id: str
) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for entry in transcript:
        if entry.agent_id == speaker_id:
            role, text = "assistant", entry.content
        else:
            role, text = "user", f"[{entry.agent_name}]: {entry.content}"
        if history and history[-1]["role"] == role:
            history[-1]["content"] += "\n\n" + text
        else:
            history.append({"role": role, "content": text})

    if not history or history[0]["role"] != "user":
        history.insert(0, {"role": "user", "content": CONVERSATION_START_NOTE})

    return [{"role": "system", "content": system_prompt}, *history]
