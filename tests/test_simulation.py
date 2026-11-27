import asyncio
from collections import Counter

from backend.openrouter.client import Completion, LLMError
from backend.persona.persona_agent import PersonaAgent
from backend.persona.persona_human import PersonaHuman
from backend.runs.config_builder import AIAgentInput, ExperimentRequest, HumanAgentInput, build_run_configuration
from backend.simulation.engine import run_simulation
from backend.simulation.ordering import build_schedule
from backend.simulation.prompts import build_messages, build_system_prompt


def make_config(rounds=3, ordering="sequential", n_agents=3):
    request = ExperimentRequest(
        rounds=rounds,
        ordering=ordering,
        human_agent=HumanAgentInput(
            persona_agent=PersonaAgent(model="openai/gpt-6-luna"),
            persona_human=PersonaHuman(personal_background="Student"),
        ),
        agents=[AIAgentInput(persona_agent=PersonaAgent(model="openai/gpt-5-nano")) for i in range(n_agents)],
    )
    return build_run_configuration(request, llm_provider="test")


class EchoClient:
    def __init__(self, fail_at=None, stop_after=None):
        self.calls = 0
        self.fail_at = fail_at

    async def complete(self, model, messages, temperature, max_tokens, timeout, **kwargs):
        self.calls += 1
        if self.fail_at and self.calls == self.fail_at:
            raise LLMError("invalid_model", "Invalid model")
        return Completion(content=f"reply {self.calls}", model=model, usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}, cost=0.01)


def test_sequential_schedule():
    config = make_config(rounds=2, ordering="sequential", n_agents=2)
    ids = [t.agent_id for t in build_schedule(config)]
    assert ids == ["human_agent", "agent_1", "agent_2"] * 2


def test_randomized_schedule_human_first_and_each_agent_once():
    config = make_config(rounds=20, ordering="randomized", n_agents=4)
    schedule = build_schedule(config)
    assert len(schedule) == config.total_turns
    orders = set()
    for r in range(1, 21):
        turns = [t.agent_id for t in schedule if t.round == r]
        assert turns[0] == "human_agent"
        assert Counter(turns[1:]) == Counter(a.id for a in config.agents)
        orders.add(tuple(turns))
    assert len(orders) > 1
    # Same seed -> same schedule.
    assert build_schedule(config) == schedule


def test_engine_completes_and_starts_with_initial_message():
    config = make_config(rounds=2, n_agents=2)
    client = EchoClient()
    result = asyncio.run(run_simulation(config, client))
    assert result.status == "completed"
    assert result.completed_turns == result.total_turns == 6
    first = result.transcript[0]
    assert first.agent_id == "human_agent" and first.source == "initial_message"
    assert first.content == config.initial_message
    assert client.calls == 5  # initial message is not generated
    assert result.usage.total_tokens == 15


def test_engine_stop_keeps_partial_transcript():
    config = make_config(rounds=3, n_agents=2)
    state = {"n": 0}

    def on_done(entry, completed, total):
        state["n"] = completed

    result = asyncio.run(run_simulation(config, EchoClient(), should_stop=lambda: state["n"] >= 4, on_turn_complete=on_done))
    assert result.status == "stopped"
    assert result.completed_turns == 4


def test_engine_failure_records_error():
    config = make_config(rounds=2, n_agents=2)
    result = asyncio.run(run_simulation(config, EchoClient(fail_at=2)))
    assert result.status == "failed"
    assert result.completed_turns == 2
    assert result.errors[0].kind == "invalid_model"


def test_messages_roles_from_speaker_view():
    config = make_config(rounds=2, n_agents=1)
    result = asyncio.run(run_simulation(config, EchoClient()))
    human = config.human_agent
    messages = build_messages(build_system_prompt(human, config), result.transcript[:2], human.id)
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert "Student" in messages[0]["content"]
    ai_prompt = build_system_prompt(config.agents[0], config)
    assert "Student" not in ai_prompt  # AI agents never see persona_human


def test_shutdown_saves_partial_result(tmp_path):
    from backend.openrouter.mock_client import MockLLMClient
    from backend.runs.run_manager import RunManager
    from backend.storage.local_storage import LocalResultStorage

    async def scenario():
        storage = LocalResultStorage(tmp_path)
        manager = RunManager(llm=MockLLMClient(delay_seconds=0.05), storage=storage)
        record = manager.prepare("sid", "carol", make_config(rounds=50, n_agents=2))
        manager.start(record.run_id, "sid")
        await asyncio.sleep(0.4)
        assert manager.has_active_runs()
        await manager.shutdown()
        assert not manager.has_active_runs()
        return record, await storage.load_result(record.result_id)

    record, doc = asyncio.run(scenario())
    assert record.storage_status == "saved"
    assert doc["status"] == "failed"
    assert doc["errors"][0]["kind"] == "server_restart"
    assert 0 < len(doc["transcript"]) < 150
    assert doc["progress"]["completed_turns"] == len(doc["transcript"])


def test_generator_parses_fenced_json():
    from backend.persona.generator import _parse_json_object

    assert _parse_json_object('```json\n{"ethics": "Care ethics."}\n```') == {"ethics": "Care ethics."}


def test_round_scoring_is_normalized_and_discounted():
    from backend.evaluation.scoring import aggregate

    keys = ["a", "b"]
    rated = [
        {"round": 1, "ratings": {"a": 5, "b": 5}, "agents": {"x": {"agent_name": "X", "ratings": {"a": 5, "b": 1}}}},
        {"round": 2, "ratings": {"a": 3, "b": 1}, "agents": {"x": {"agent_name": "X", "ratings": {"a": 1, "b": 1}}}},
    ]
    turns, scores = aggregate(rated, keys, discount=0.9, scale_min=1, scale_max=5)
    assert [t["turn_score"] for t in turns] == [1.0, 0.25]
    w1, w2 = 1 / 1.9, 0.9 / 1.9
    assert abs(scores["overall"]["discounted"] - (w1 * 1.0 + w2 * 0.25)) < 1e-3
    assert abs(sum(scores["round_weights"].values()) - 1) < 1e-3
    assert scores["by_criterion"]["b"]["by_round"] == {"1": 1.0, "2": 0.0}
    assert scores["by_agent"]["x"]["by_round"] == {"1": 0.5, "2": 0.0}
    # discount = 1 is a plain average over rounds
    _, plain = aggregate(rated, keys, discount=1.0, scale_min=1, scale_max=5)
    assert plain["overall"]["discounted"] == plain["overall"]["mean"] == 0.625
