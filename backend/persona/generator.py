"""Generates persona field text with an LLM (used by the "Random" buttons).

Which fields can be generated is declared on the persona models with
`persona_field(..., generatable=True)`.
"""

from __future__ import annotations

import json
import random
import re

from pydantic import BaseModel

from backend.config import generation_prompts as prompts
from backend.config.simulation_defaults import PERSONA_GENERATOR_MODEL
from backend.openrouter.client import LLMClient, LLMError, complete_with_retries
from backend.persona.fields import generatable_fields, persona_to_prompt_text


class GenerationError(Exception):
    pass


def _field_list(model_cls: type[BaseModel], names: list[str]) -> str:
    lines = []
    for name in names:
        info = model_cls.model_fields[name]
        hint = f" (for example: {info.json_schema_extra.get('placeholder')})" if isinstance(info.json_schema_extra, dict) and info.json_schema_extra.get("placeholder") else ""
        lines.append(f"- {name}: {info.title or name}{hint}")
    return "\n".join(lines)


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise GenerationError("The model did not return a JSON object.")
    try:
        data = json.loads(match.group(0))
    except ValueError:
        raise GenerationError("The model returned invalid JSON.") from None
    if not isinstance(data, dict):
        raise GenerationError("The model returned an unexpected format.")
    return data


async def generate_persona_fields(
    llm: LLMClient,
    *,
    model_cls: type[BaseModel],
    field_names: list[str],
    agent_kind: str,
    context: BaseModel | None,
    scenario: str = "",
) -> dict[str, str]:
    """Return {field_name: generated text} for the requested generatable fields."""
    allowed = generatable_fields(model_cls)
    names = [name for name in field_names if name in allowed] if field_names else allowed
    if not names:
        raise GenerationError("No generatable fields were requested.")

    context_text = persona_to_prompt_text(context, exclude=names) if context is not None else "- (none)"
    user_prompt = prompts.USER_PROMPT.format(
        subject=prompts.SUBJECTS.get(agent_kind, prompts.SUBJECTS["human"]),
        scenario=scenario.strip() or "(none)",
        context=context_text,
        field_list=_field_list(model_cls, names),
        keys=", ".join(names),
        seed=random.randrange(1_000_000),
    )
    messages = [
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    try:
        completion = await complete_with_retries(
            llm,
            model=PERSONA_GENERATOR_MODEL,
            messages=messages,
            temperature=1.0,
            max_tokens=4000,
            timeout=90,
            max_attempts=2,
            reasoning_effort="low",
            json_output=True,
        )
    except LLMError as exc:
        raise GenerationError(exc.message) from None

    data = _parse_json_object(completion.content)
    values = {name: str(data.get(name, "")).strip() for name in names}
    if not any(values.values()):
        raise GenerationError("The model returned empty values.")
    return values
