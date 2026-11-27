"""Rubric used to score every run (exploratory). Edit freely.

Unit of scoring = one ROUND (the Human Agent's message plus every AI Agent's
reply in that round), not a single message.

After a run, EVALUATOR_MODEL rates each round in a SEPARATE call (it sees the
conversation up to and including that round), with integers SCALE_MIN..SCALE_MAX
and a short evidence note for every rating group:

  * CRITERIA        - the AI agents: the round as a whole and each AI agent's own reply
  * HUMAN_CRITERIA  - the simulated human (a check on the simulator itself)

Every criterion has anchors for 1 / 3 / 5 so that ratings use the whole scale.
Everything is then normalized to 0..1 and discounted per round:

    n(x)          = (x - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)
    round_score_t = mean over criteria of n(round rating)
    w_t           = DISCOUNT**(t-1) / sum_k DISCOUNT**(k-1)          (weights sum to 1)
    overall       = sum_t w_t * round_score_t                         (0..1)

The same discounted average is reported per criterion, per agent and per
agent x criterion. The human check is reported separately and is NOT part of
"overall". The rubric, discount and evaluator model are stored in each result.
"""

RUBRIC_ENABLED = True
EVALUATOR_MODEL = "openai/gpt-6-luna"
EVALUATOR_REASONING_EFFORT = "medium"
EVALUATOR_CONCURRENCY = 3  # rounds rated in parallel

SCALE_MIN = 1
SCALE_MAX = 5
DISCOUNT = 0.9

# AI agents (rated for the round as a whole and for each AI agent's own replies).
CRITERIA = [
    {
        "key": "candor",
        "description": "Says what the persona really thinks and feels about the situation.",
        "levels": {
            1: "Polite, generic, safe statements anyone could say; no personal stake.",
            3: "Some personal opinion, but hedged, abstract or softened.",
            5: "Clearly personal and specific, including uncomfortable feelings or disagreement, consistent with the persona.",
        },
    },
    {
        "key": "distinctness",
        "description": "Adds a perspective that is different from what others already said.",
        "levels": {
            1: "Repeats or paraphrases what others already said; replies converge on the same point.",
            3: "Partly new, partly overlapping with earlier replies.",
            5: "Each reply adds a clearly different view grounded in the speaker's own persona.",
        },
    },
    {
        "key": "attunement",
        "description": "Notices and responds to the simulated human's state and cues (including indirect ones), relative to the cues actually given.",
        "levels": {
            1: "Ignores clear cues, dismisses them, or lectures and moralizes.",
            3: "Responds only to the surface content; no sign of noticing the person behind it (also the default when there were no cues).",
            5: "Picks up subtle cues and responds with care and tact, without being preachy.",
        },
    },
    {
        "key": "interaction",
        "description": "Engages with what other participants actually said (agrees, disagrees, asks, builds on, reacts), instead of only answering the question in isolation.",
        "levels": {
            1: "Each reply stands alone, as if answering a questionnaire; no reference to anyone else's words.",
            3: "Occasional reference to another participant, mostly to the question-asker.",
            5: "Replies clearly react to specific people's words or behavior, so the participants talk with each other.",
        },
    },
    {
        "key": "naturalness",
        "description": "Sounds like real spoken conversation in this situation, not like a written, templated or overly polished answer.",
        "levels": {
            1: "Templated or essay-like: same sentence pattern as others, neatly structured, overly articulate.",
            3: "Mostly spoken, but somewhat polished or formulaic.",
            5: "Varied and spoken, with the hesitation, emphasis and imperfection of real speech for this persona.",
        },
    },
]

# The simulated human (rated per round in which it produced a generated message).
HUMAN_CRITERIA = [
    {
        "key": "human_realism",
        "description": "Sounds like a real person in this situation, not like an AI assistant or a moderator.",
        "levels": {
            1: "Assistant- or moderator-like: summarizes everyone, lists points, proposes action plans, polished.",
            3: "Mostly natural, but at times assistant-like or too composed.",
            5: "Convincingly human: personal reactions, hesitation, imperfection that fit the persona.",
        },
    },
    {
        "key": "private_state_expression",
        "description": "The private situation (Human Persona) plausibly shapes how the person talks, so that an attentive listener could notice it.",
        "levels": {
            1: "No trace of the private situation at all.",
            3: "Faint hints that only someone who knows the persona would notice.",
            5: "Clearly shapes tone and behavior in a plausible, mostly indirect way (dumping everything at once is not a 5).",
        },
    },
    {
        "key": "agency",
        "description": "Pursues their own concerns and reacts from their own values, instead of following others' suggestions or accepting every point.",
        "levels": {
            1: "Follows the question or direction suggested by someone else, or accepts every criticism at once like an ideal listener.",
            3: "Some own direction, but largely led by others or uniformly agreeable.",
            5: "Clearly drives from their own concerns and values, including defending, doubting or resisting when this persona would.",
        },
    },
]

SYSTEM_PROMPT = (
    "You are a strict, consistent evaluator of simulated multi-party conversations in a research study. "
    "Rate against the anchored rubric and use the whole scale: 3 is an ordinary, acceptable reply; "
    "give 5 only when the description of 5 clearly applies. Giving 5 for everything is almost never justified. "
    "Judge each participant on their own message; do not give everyone the same ratings by default. "
    "Return only a JSON object, with no markdown."
)

USER_PROMPT = """Evaluate ONE round of the conversation below: round {round}. A round is the simulated human's message plus all replies by the AI participants in that round. Earlier rounds are context only; do not rate them.

Scenario and shared rules:
{scenario}

Participants:
{participants}

Transcript up to round {round} (#sequence, round, speaker):
{transcript}

Rubric for the AI participants (integers {scale_min}-{scale_max}; anchors for 1 / 3 / 5):
{criteria}

Rubric for the simulated human {human_name} (integers {scale_min}-{scale_max}; anchors for 1 / 3 / 5):
{human_criteria}

Rate round {round}:
- "scores": ratings for the AI participants' replies in round {round} as a whole;
- "agents": ratings for each AI participant's own reply in round {round}, keyed by name, each with "evidence": one short sentence quoting or pointing to the words that justify the ratings;
- "human": {human_instruction}
- "note": one or two short sentences on the main reasons for the round ratings.

Return a JSON object of the form:
{{"round": {round}, "scores": {{{score_keys}}}, "agents": {{"<name>": {{{score_keys}, "evidence": "<text>"}}}}, "human": {human_shape}, "note": "<text>"}}
Round: {round}
Criteria: {criteria_keys}
Human criteria: {human_criteria_keys}
Rate human: {rate_human}
Agents: {agent_names}"""
