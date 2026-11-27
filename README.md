# MASS — Multi Agent System Simulator

A research prototype for running LLM-driven multi-agent conversations.

Every participant is simulated. The **Human Agent** is an LLM that role-plays a
person (`persona_agent` + `persona_human`). Up to 10 **AI Agents** respond to it
(`persona_agent` only). All models are called through OpenRouter. Each run
produces one JSON file that is saved to `results/` in a GitHub repository.

```
Login → Home → Run Experiment → configure agents → run → JSON → saved to GitHub → Check Result
```

Collaborators only need the shared URL and the shared password.

---

## Architecture

```
Browser (HTML/CSS/JS, no build step)
   │  same-origin JSON API, session cookie
   ▼
FastAPI backend (Python)
   ├── simulation engine ──► OpenRouter   (OPENROUTER_API_KEY stays on the server)
   └── result storage    ──► GitHub API   (GITHUB_TOKEN stays on the server)
```

```
backend/
  main.py                    App setup (session middleware, routers, static files)
  settings.py                Environment variables
  auth/session.py            Shared-password login, signed session cookie
  api/                       HTTP routes (auth, experiment/runs, results, pages)
  persona/
    persona_agent.py         persona_agent definition (all agents)
    persona_human.py         persona_human definition (Human Agent only)
    fields.py                Field helper: validation + editor form + prompt text
  config/
    initial_message.py       First message of every run (sent by the Human Agent)
    prompts.py               System prompt templates
    simulation_defaults.py   Default model, temperature, limits, retries
  simulation/
    types.py                 RunConfiguration, TranscriptEntry, SimulationResult
    ordering.py              Sequential / randomized speaking order
    prompts.py               Builds chat messages for one agent turn
    engine.py                run_simulation(config, llm) -> SimulationResult
  openrouter/
    client.py                OpenRouter client, error mapping, retries
    mock_client.py           Offline client (LLM_PROVIDER=mock)
    model_catalog.py         Cached model list for suggestions and validation
  runs/
    config_builder.py        Browser request -> frozen RunConfiguration
    run_manager.py           Background runs, stop, progress, save, retry save
  results/
    schema.py                Result JSON document
    naming.py                Run IDs and result filenames
  storage/
    result_storage.py        ResultStorage interface + factory
    github_storage.py        GitHub implementation (default)
    local_storage.py         Local-disk implementation (development)
frontend/
  pages/                     login, home, run, results, result (HTML shells)
  static/css/                Design tokens, components, page styles
  static/js/core/            API wrapper, DOM helper, icons, header, modal/drawer
  static/js/run/             Run Experiment page modules
  static/js/results/         Result list, JSON viewer, transcript view
tests/                       pytest suite
scripts/run_batch_example.py Using the engine without the UI
results/                     Saved result JSON files (written by the app)
```

The simulation engine does not know about the UI, sessions, or storage.
Storage can be replaced (S3, R2, Supabase, a database) by adding a class with
`save_result`, `list_results` and `load_result` and returning it from
`get_result_storage()` in `backend/storage/result_storage.py`.

---

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # then edit .env
uvicorn backend.main:app --reload
```

Open http://localhost:8000.

To try the full flow without any API keys, set in `.env`:

```
APP_PASSWORD=test
LLM_PROVIDER=mock
STORAGE_BACKEND=local
```

Run the tests:

```bash
pytest
```

---

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `APP_PASSWORD` | yes | Shared login password. Checked on the server only. |
| `SESSION_SECRET` | yes (prod) | Long random string used to sign session cookies. |
| `SESSION_COOKIE_SECURE` | prod | `true` when served over HTTPS. |
| `OPENROUTER_API_KEY` | yes | OpenRouter API key. |
| `LLM_PROVIDER` | no | `openrouter` (default) or `mock`. |
| `APP_PUBLIC_URL` | prod | Public URL of the app. Used as the OpenRouter referer and for the keep-alive ping. |
| `KEEP_ALIVE_WHILE_RUNNING` | no | `true` (default): ping `APP_PUBLIC_URL` every 5 min while a run is active. |
| `OPENROUTER_VALIDATE_MODELS` | no | `true` (default): reject unknown model ids before a run starts. |
| `STORAGE_BACKEND` | no | `github` (default) or `local`. |
| `GITHUB_TOKEN` | yes | Fine-grained token with *Contents: Read and write* on the repository. |
| `GITHUB_OWNER` | yes | Repository owner (user or organization). |
| `GITHUB_REPO` | yes | Repository name. |
| `GITHUB_BRANCH` | no | Branch to write results to (default `main`). |
| `GITHUB_RESULTS_DIR` | no | Directory for results (default `results`). |

Secrets are never sent to the browser, written into results, or logged.

---

## Setup guides

### OpenRouter

1. Create an account at https://openrouter.ai and add credits.
2. Create a key at https://openrouter.ai/settings/keys.
3. Set it as `OPENROUTER_API_KEY` on the server.
4. Agents can use the models listed in `MODEL_OPTIONS` in
   `backend/config/simulation_defaults.py` (currently `openai/gpt-5-nano`,
   `openai/gpt-5.6-luna`, `openai/gpt-6-luna`; default `openai/gpt-5.6-luna`).
   Edit that list to offer other OpenRouter models.

### Random persona text

The **Random** buttons in the persona editor (Ethics, and the whole Human
Persona section) ask `PERSONA_GENERATOR_MODEL` (`openai/gpt-6-luna`) to write
text that fits the persona's other details, and fill it into the form. Nothing
is applied until **Save**. Prompts are in `backend/config/generation_prompts.py`.
Fields get a Random button when declared with `persona_field(..., generatable=True)`.

### GitHub token

1. GitHub → Settings → Developer settings → Personal access tokens →
   **Fine-grained tokens** → Generate new token.
2. Repository access: **Only select repositories** → this repository.
3. Permissions → Repository permissions → **Contents: Read and write**.
4. Set the token as `GITHUB_TOKEN`, and set `GITHUB_OWNER` / `GITHUB_REPO`.

Each result is created as a new file with a commit message
`Add experiment result <result id>`. Existing files are never overwritten.

---

## Deployment

Runs can take several minutes (rounds × agents model calls), so deploy as a
long-running web service, **not** as serverless functions (e.g. Vercel /
Netlify functions), whose request time limits would cut runs off.

The run manager keeps active runs in memory, so run **exactly one instance with
one worker**. If the server stops during a run (restart, redeploy, the host
putting the app to sleep), the partial transcript is saved with
`"status": "failed"` and an error of kind `server_restart`.

### Render Free (recommended, no cost)

1. Push this repository to GitHub.
2. Render → New → **Blueprint** → select the repository (uses `render.yaml`).
3. Fill in `APP_PASSWORD`, `OPENROUTER_API_KEY`, `GITHUB_TOKEN`,
   `GITHUB_OWNER`, `GITHUB_REPO`.
4. After the first deploy, copy the `https://<service>.onrender.com` URL into
   `APP_PUBLIC_URL` and save (this triggers one redeploy).
5. Share the URL and the password with collaborators.

What to expect on the free plan:

- The app sleeps after 15 minutes without requests. The first visit after
  that takes up to about a minute to load.
- While a run is active, the app requests its own `APP_PUBLIC_URL` every
  5 minutes so it is not put to sleep mid-run, even if the browser is closed.
- Render may still restart free services occasionally; the partial result is
  saved when that happens.
- Free hours per month (750) cover one service running all month.

`render.yaml` ignores changes under `results/`, so commits created by saving
results do not trigger a redeploy.

### Your own computer + Cloudflare Tunnel (no cost, no sleeping)

Run the app locally (see *Run locally*) and expose it with
`cloudflared tunnel --url http://localhost:8000`. This prints a public
`https://….trycloudflare.com` URL. The computer must stay on, and the URL
changes each time the tunnel restarts.

### Any Docker host (Railway, Fly.io, a VM, ...)

```bash
docker build -t mass .
docker run -p 8000:8000 --env-file .env mass
```

If results are saved to the same repository the host deploys from, disable
auto-deploy for changes under `results/`, or point `GITHUB_REPO` at a separate
results repository.

---

## Simulation behavior

- Each **round**, every agent speaks once. The Human Agent always speaks first.
- **Sequential**: Human Agent → Agent 1 → Agent 2 → …
- **Randomized**: Human Agent → a new random permutation of the AI Agents each
  round. The permutation is drawn from `random_seed`, stored in the result.
- Round 1 starts with the experiment's **Initial Message** (Scenario editor;
  default in `backend/config/initial_message.py`), which counts as the Human
  Agent's first turn. Total turns = `rounds × (1 + number of AI Agents)`.
- The **Scenario** (setting, topic and shared rules) is shown to every agent.
  Private details of the simulated human go in the Human Persona, which only
  the Human Agent sees. Prompts are topic-agnostic; the topic comes from the
  Scenario.
- Agents can have a **Name** (persona_agent `name`); it is used in the
  transcript and in prompts. Empty names default to "Human Agent" / "Agent N".
- Each agent sees the conversation from its own point of view: its own
  messages as `assistant`, everyone else's as `user` prefixed with
  `[Agent name]:`. System prompts come from `backend/config/prompts.py`.
- **Stop**: no new turn starts; the turn in flight finishes, and a partial
  result with `"status": "stopped"` is saved.
- Rate limits, timeouts and provider errors are retried (up to 4 attempts per
  turn; after a rate limit the wait grows 15 s, 30 s, 45 s).
  If a turn still fails, the run ends with `"status": "failed"` and the
  partial transcript is saved.
- Simulation status and upload status are separate. If the upload fails, the
  completion dialog offers **Retry Save** and **Download JSON** without
  re-running the experiment.

## Rubric scoring (exploratory)

The unit is a **round** (the Human Agent's message plus every AI Agent's reply),
not a single message. After every run, `EVALUATOR_MODEL` (`openai/gpt-6-luna`)
rates each round in a **separate call** (it sees the conversation up to that
round, so it cannot copy one set of numbers across the run). Ratings are
integers (1–5) on the anchored rubric in `backend/config/rubric.py` (each
criterion describes what 1, 3 and 5 mean), and every agent's ratings come with
a one-sentence **evidence** note:

- **AI agents**: `candor`, `distinctness`, `attunement`, `interaction`
  (talks with the others, not only answers the question), `naturalness`
  (spoken, not templated or polished), rated for the round as a whole and for
  each AI agent's own reply;
- **Simulated human** (simulator check, not part of the overall score):
  `human_realism`, `private_state_expression`, `agency` (drives from its own
  concerns instead of following others' suggestions), for rounds where the
  Human Agent produced a generated message (its first message is a fixed script).

Everything is normalized to 0–1 and discounted per round:

```
n(x)          = (x - 1) / (5 - 1)                         0 = worst, 1 = best
round_score_t = mean over criteria of n(round rating)
w_t           = γ^(t-1) / Σ_k γ^(k-1)                     weights sum to 1 (γ = DISCOUNT = 0.9)
overall       = Σ_t w_t · round_score_t                   0..1, comparable across run lengths
```

`γ = 1` is a plain average over rounds; `γ < 1` weights early rounds more.
The same discounted average is reported per criterion, per agent, per
agent × criterion, and for the simulated human. The result page has a
**Scores** tab with these tables; the result JSON stores everything under
`"evaluation"` (ratings, normalized values, weights, notes, the rubric itself).
Set `RUBRIC_ENABLED = False` to turn scoring off.

## Import / Export and batches

- **Export** downloads the current configuration as JSON.
- **Import** accepts:
  - one experiment, or `{"experiments": [ ... ]}` with several experiments;
  - a saved result file (re-runs its exact configuration).
- Each experiment may set `"repeats"`. One run in total loads into the editor;
  more than one becomes a **batch**: runs execute one after another on the
  server (up to 50), each saved as its own result file with
  `"batch": {"batch_id", "index", "size"}`.
- Examples (Japanese): `examples/mid_managers_vent_ja.json`, `older_managers_ja.json`,
  `compliance_guidance_ja.json`, `young_voices_ja.json`, and `all_scenarios_ja.json`
  (all four as one batch). Each also has a version without the facilitator:
  `*_nofac_ja.json` and `all_scenarios_nofac_ja.json`.

Experiment format:

```json
{
  "experiments": [{
    "label": "my_experiment", "repeats": 1, "rounds": 3, "ordering": "sequential",
    "scenario": "...", "initial_message": "...",
    "human_agent": {"persona_agent": {...}, "persona_human": {...}},
    "agents": [{"persona_agent": {...}}]
  }]
}
```

Missing persona fields get defaults; unknown fields are ignored. Older files
with `mental_wellbeing_context` are merged into `additional_context`.

## Critical mass experiment (exploratory)

`examples/critical_mass/` holds a "critical mass" design on the young_voices
setting without a facilitator: 佐藤課長 asks **8 juniors** for their honest
views; **k** of them are *committed* (they have decided to speak frankly
whatever the others do), the other 8−k are *cautious* (same kind of real
grievances, but they read the room). Only k changes (0, 1, 2, 3, 4, 6, 8);
the committed set is nested, the order of the juniors is randomized every
round, and nothing tells the cautious juniors how many others must speak
first. 4 rounds per run.

- `cm_young_all.json` imports all 7 conditions as one batch; `cm_young_k{k}of8.json` is one condition.
- `python -m scripts.make_critical_mass --repeats 3` regenerates the files with 3 runs per condition.
- After `git pull`, `python -m scripts.critical_mass_summary` prints, per k, the
  candor of the cautious and committed juniors (overall and per round) and the
  simulated human's check scores; `--csv cm.csv` writes one row per run.

## Result JSON

```
{
  "schema_version": "1.1",
  "run_id": "run_a83f2c",
  "username": "alice",
  "label": "young_voices_ja",
  "batch": null,
  "created_at": "...", "started_at": "...", "completed_at": "...",
  "status": "completed | stopped | failed",
  "stop_reason": null,
  "progress": { "completed_turns": 12, "total_turns": 12 },
  "configuration": {
    "label", "rounds", "ordering", "random_seed", "scenario", "initial_message", "llm_provider",
    "human_agent": { "id", "name", "agent_type", "persona_agent", "persona_human" },
    "agents": [ { "id", "name", "agent_type", "persona_agent" } ],
    "generation": { "temperature", "max_tokens", ... },
    "prompt_templates": { ... }
  },
  "transcript": [
    { "round", "sequence", "position_in_round", "agent_id", "agent_name",
      "agent_type", "model", "content", "timestamp", "source",
      "response_model", "provider", "generation_id", "finish_reason",
      "latency_ms", "attempts", "usage", "cost" }
  ],
  "usage": { "prompt_tokens", "completion_tokens", "total_tokens", "cost" },
  "errors": [ { "kind", "message", "round", "sequence", "agent_id", "timestamp" } ],
  "evaluation": { "status", "rubric", "evaluator_model", "scores", "turns" }
}
```

Filename: `results/{run name}--{username}_{YYYY-MM-DDTHH-MM-SS}_{run_id}.json`
(UTC), e.g. `young_voices_nofac_ja--ren_2026-10-14T09-00-00_run_1a2b3c.json`.
The run name is the experiment's `label` (the **Run name** field on the Run
page); without one the file is `{username}_{...}_{run_id}.json`. Only letters,
digits, `-` and `_` go into the filename, so a name in Japanese is kept inside
the JSON but not in the filename. The run_id keeps every filename unique.

## Changing personas

- **Add a `persona_agent` field**: add one `persona_field(...)` line to
  `backend/persona/persona_agent.py`. The editor, summary, validation, result
  JSON and system prompt all pick it up.
- **Change `persona_human`**: edit `backend/persona/persona_human.py` only.
  AI Agents never use it.
- Widgets: `text`, `textarea`, `number`, `select` (with `options`; values are
  validated against the list), `combo` (with `suggestions`; choose from the list
  or type freely). Lists live in `backend/persona/options.py`.
- `in_prompt=False` keeps a field out of the system prompt;
  `generatable=True` adds a Random button.

## Known limitations

- Active runs are kept in memory (single instance, lost on restart).
- The GitHub contents API lists up to 1,000 files per directory.
- The shared password is a single secret for everyone; usernames are labels,
  not accounts.
