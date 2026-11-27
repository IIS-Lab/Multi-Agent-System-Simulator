"""persona_agent: the general persona shared by every simulated agent.

Used by both the Human Agent and every AI Agent.

To add a new field, add one `persona_field(...)` line below. The editor form,
validation, experiment summary, result JSON and system prompt pick it up
automatically.
"""

from __future__ import annotations

from backend.config.simulation_defaults import DEFAULT_MODEL, MODEL_OPTIONS
from backend.persona.fields import PersonaModel, persona_field
from backend.persona.options import GENDER_OPTIONS, NATIONALITY_OPTIONS


class PersonaAgent(PersonaModel):
    name: str = persona_field(
        "",
        label="Name",
        placeholder="Optional, e.g. Suzuki",
        help_text="Shown in the conversation. Leave empty to use Human Agent / Agent N.",
        in_prompt=False,
        max_length=60,
    )
    age: int = persona_field(30, label="Age", widget="number", ge=1, le=120)
    gender: str = persona_field("Unspecified", label="Gender", widget="select", options=GENDER_OPTIONS)
    nationality: str = persona_field(
        "",
        label="Nationality",
        widget="combo",
        suggestions=NATIONALITY_OPTIONS,
        placeholder="Type or choose (optional)",
        max_length=100,
    )
    profile: str = persona_field(
        "",
        label="Profile",
        widget="textarea",
        placeholder="Role, background and personality, e.g. 25-year-old engineer who values work-life balance",
        generatable=True,
        max_length=8000,
    )
    ethics: str = persona_field(
        "",
        label="Ethics",
        widget="textarea",
        placeholder="e.g., Utilitarian; prioritizes safety and autonomy",
        generatable=True,
        max_length=4000,
    )
    language: str = persona_field("English", label="Language", placeholder="e.g., English", max_length=100)
    model: str = persona_field(
        DEFAULT_MODEL,
        label="Model",
        widget="select",
        options=MODEL_OPTIONS,
        help_text="OpenRouter model used for this agent.",
        in_prompt=False,
    )
