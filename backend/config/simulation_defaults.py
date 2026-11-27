"""Default simulation parameters. Edit these values to change defaults.

Every value used by a run is copied into the run's configuration snapshot, so
results stay reproducible even after these defaults change.
"""

# Models agents can use (OpenRouter ids). Shown as a dropdown in the persona editor.
MODEL_OPTIONS = [
    "openai/gpt-5-nano",
    "openai/gpt-5.6-luna",
    "openai/gpt-6-luna",
]

# Model selected for new agents. Must be one of MODEL_OPTIONS.
DEFAULT_MODEL = "openai/gpt-5.6-luna"

# Model used by the "Random" buttons that generate Ethics / Human Persona text.
PERSONA_GENERATOR_MODEL = "openai/gpt-6-luna"

DEFAULT_ROUNDS = 3
MAX_ROUNDS = 100
MAX_AI_AGENTS = 10

# Generation parameters sent to OpenRouter for every agent turn.
TEMPERATURE = 0.8
# Upper limit on tokens per reply. For reasoning models this budget also covers
# hidden reasoning tokens, so it is set well above a normal chat reply length.
MAX_TOKENS = 4000
# Reasoning effort for models that support it ("minimal", "low", "medium",
# "high"), or None to use each model's default. Ignored by other models.
REASONING_EFFORT = "low"

# Request handling.
REQUEST_TIMEOUT_SECONDS = 120
MAX_ATTEMPTS_PER_TURN = 4  # retries on rate limit / timeout / server errors
RATE_LIMIT_BACKOFF_SECONDS = 15  # wait 15s, 30s, 45s after HTTP 429
