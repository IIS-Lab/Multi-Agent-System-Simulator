"""Default first message of an experiment. It is always sent by the Human Agent.

Each experiment can set its own Initial Message (Scenario editor or imported
JSON); this value is only the default for new experiments. The message used is
copied into each run's configuration snapshot and counts as the Human Agent's
round-1 turn.
"""

INITIAL_MESSAGE = (
    "Hi everyone, thanks for making time today. There is something that has been "
    "on my mind lately, and I'd like to hear what you think."
)
