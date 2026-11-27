"""Shared helpers for persona definitions.

A persona is a plain Pydantic model. Each field is declared once with
`persona_field(...)`, which stores UI hints (label, widget, options). From that
single definition we derive:

* server-side validation (Pydantic),
* the editor form shown in the browser (`describe_fields`),
* the text rendered into agent system prompts (`persona_to_prompt_text`).

To add a persona field, add one `persona_field` line to the persona model.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def persona_field(
    default: Any,
    *,
    label: str,
    widget: str = "text",
    options: list[str] | None = None,
    suggestions: list[str] | None = None,
    placeholder: str = "",
    help_text: str = "",
    in_prompt: bool = True,
    generatable: bool = False,
    **constraints: Any,
) -> Any:
    """Declare a persona field together with its UI hints.

    widget: "text" | "textarea" | "number" | "select" | "combo"
    options: allowed values for a "select" field (validated on the server).
    suggestions: choices for a "combo" field; free typing is also allowed.
    in_prompt: whether the field is rendered into the agent's system prompt.
    generatable: show a "Random" button that fills the field with model-generated text.
    constraints: regular Pydantic constraints (ge, le, max_length, pattern, ...).
    """
    extra: dict[str, Any] = {
        "widget": widget,
        "placeholder": placeholder,
        "in_prompt": in_prompt,
        "generatable": generatable,
    }
    if options is not None:
        extra["options"] = options
    if suggestions is not None:
        extra["suggestions"] = suggestions
    if "ge" in constraints:
        extra["min"] = constraints["ge"]
    if "le" in constraints:
        extra["max"] = constraints["le"]
    return Field(default, title=label, description=help_text, json_schema_extra=extra, **constraints)


def field_extra(model_cls: type[BaseModel], name: str) -> dict[str, Any]:
    extra = model_cls.model_fields[name].json_schema_extra
    return extra if isinstance(extra, dict) else {}


class PersonaModel(BaseModel):
    """Base class for persona definitions: strict fields and select-option validation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def _check_options(self):
        for name in type(self).model_fields:
            options = field_extra(type(self), name).get("options")
            if options is not None and getattr(self, name) not in options:
                label = type(self).model_fields[name].title or name
                raise ValueError(f"{label} must be one of the listed options.")
        return self


def generatable_fields(model_cls: type[BaseModel]) -> list[str]:
    return [name for name in model_cls.model_fields if field_extra(model_cls, name).get("generatable")]


def describe_fields(model_cls: type[BaseModel]) -> list[dict[str, Any]]:
    """Return a JSON-serializable description of a persona model's fields for the UI."""
    fields = []
    for name, info in model_cls.model_fields.items():
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        fields.append(
            {
                "name": name,
                "label": info.title or name.replace("_", " ").title(),
                "widget": extra.get("widget", "text"),
                "options": extra.get("options"),
                "suggestions": extra.get("suggestions"),
                "placeholder": extra.get("placeholder", ""),
                "help": info.description or "",
                "min": extra.get("min"),
                "max": extra.get("max"),
                "generatable": bool(extra.get("generatable")),
                "default": info.get_default(call_default_factory=True),
            }
        )
    return fields


def persona_to_prompt_text(persona: BaseModel, exclude: tuple[str, ...] | list[str] = ()) -> str:
    """Render a persona as '- Label: value' lines for use inside a system prompt."""
    lines = []
    for name, info in type(persona).model_fields.items():
        if name in exclude:
            continue
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        if not extra.get("in_prompt", True):
            continue
        value = getattr(persona, name)
        text = str(value).strip() if value is not None else ""
        label = info.title or name.replace("_", " ").title()
        lines.append(f"- {label}: {text if text else 'Not specified'}")
    return "\n".join(lines)
