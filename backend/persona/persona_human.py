"""persona_human: extra persona used ONLY by the simulated Human Agent.

Private, topic-agnostic context about the simulated person: their background
and any other circumstances (including mental well-being) that shape how they
talk. Other agents never see these fields. AI Agents never depend on this module.

These fields are a first draft and are expected to change. To add, remove or
rename a field, edit this file only; the editor form, validation, summary,
result JSON and the Human Agent system prompt follow automatically.
"""

from __future__ import annotations

from pydantic import model_validator

from backend.persona.fields import PersonaModel, persona_field

# Older configurations had a separate "mental_wellbeing_context" field.
LEGACY_FIELDS = ("mental_wellbeing_context",)


class PersonaHuman(PersonaModel):
    personal_background: str = persona_field(
        "",
        label="Personal Background",
        widget="textarea",
        generatable=True,
        placeholder="e.g., Graduate student living alone in a new city",
        max_length=8000,
    )
    additional_context: str = persona_field(
        "",
        label="Additional Context",
        widget="textarea",
        generatable=True,
        placeholder="Current circumstances, worries, mental well-being, anything else that shapes how this person talks",
        max_length=8000,
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_legacy_fields(cls, data):
        """Fold legacy fields into additional_context so old JSON files still import."""
        if isinstance(data, dict) and any(key in data for key in LEGACY_FIELDS):
            data = dict(data)
            parts = [data.pop(key, "") for key in LEGACY_FIELDS] + [data.get("additional_context", "")]
            data["additional_context"] = "\n\n".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
        return data
