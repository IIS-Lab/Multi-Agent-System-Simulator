"""Prompts for the "Random" buttons that generate persona text. Edit freely.

Placeholders:
  {subject}      who the text describes (see SUBJECTS)
  {scenario}     the experiment's Scenario (may be empty)
  {context}      persona details already filled in ("- Age: 30" ...)
  {field_list}   the fields to write, with a short hint for each
  {keys}         comma-separated JSON keys expected in the answer
  {seed}         random number that nudges the model toward varied outputs
"""

SYSTEM_PROMPT = (
    "You write realistic, specific persona details for a research simulation of "
    "multi-party conversations. Return only a JSON object, with no markdown and no extra text."
)

SUBJECTS = {
    "human": "the simulated human participant (the person whose situation the conversation is about)",
    "ai": "one of the other participants in the conversation",
}

USER_PROMPT = """Write persona details for {subject}.

Scenario of the conversation (may be empty):
{scenario}

Details already decided (stay consistent with them; if a detail is empty or "Unspecified", choose freely):
{context}

Write a value for each of these fields:
{field_list}

Rules:
- Each value is 1-3 sentences.
- Write in the persona's language if one is given above; otherwise in English.
- Fit the scenario. Be concrete and varied; avoid generic or stereotypical descriptions.
- Do not include names of real people.
- Variation seed: {seed}

Answer with a JSON object whose keys are exactly the field keys below and whose values are strings.
Keys: {keys}"""
