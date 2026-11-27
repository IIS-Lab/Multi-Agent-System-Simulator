import os
import time

os.environ.update(
    {
        "APP_PASSWORD": "test-password",
        "SESSION_SECRET": "test-secret",
        "LLM_PROVIDER": "mock",
        "STORAGE_BACKEND": "local",
        "LOCAL_RESULTS_DIR": "local_results_test",
    }
)

import copy  # noqa: E402
import shutil  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import create_app  # noqa: E402
from backend.openrouter.mock_client import MockLLMClient  # noqa: E402
from backend.settings import PROJECT_ROOT  # noqa: E402


def make_client():
    shutil.rmtree(PROJECT_ROOT / "local_results_test", ignore_errors=True)
    app = create_app()
    app.state.run_manager._llm = MockLLMClient(delay_seconds=0.01)
    return TestClient(app)


def payload(rounds=2):
    return copy.deepcopy(_payload(rounds))


def _payload(rounds):
    def agent():
        return {"age": 40, "gender": "Female", "nationality": "Japanese", "ethics": "Care ethics", "language": "English", "model": "openai/gpt-5.6-luna"}

    return {
        "rounds": rounds,
        "ordering": "randomized",
        "human_agent": {"persona_agent": agent(), "persona_human": {"personal_background": "x", "mental_wellbeing_context": "", "additional_context": ""}},
        "agents": [{"persona_agent": agent()}, {"persona_agent": agent()}],
    }


def test_login_required_and_wrong_password():
    with make_client() as client:
        assert client.get("/api/experiment/schema").status_code == 401
        assert client.get("/run", follow_redirects=False).status_code == 303
        r = client.post("/api/auth/login", json={"username": "alice", "password": "nope"})
        assert r.status_code == 401 and r.json()["detail"] == "Incorrect password."
        r = client.post("/api/auth/login", json={"username": "  ", "password": "test-password"})
        assert r.status_code == 400


def test_full_run_flow():
    with make_client() as client:
        assert client.post("/api/auth/login", json={"username": "alice b/../", "password": "test-password"}).status_code == 200
        schema = client.get("/api/experiment/schema").json()
        assert [f["name"] for f in schema["persona_agent_fields"]] == ["name", "age", "gender", "nationality", "profile", "ethics", "language", "model"]
        assert [f["name"] for f in schema["persona_human_fields"]] == ["personal_background", "additional_context"]

        bad = payload()
        bad["rounds"] = 0
        assert client.post("/api/runs/prepare", json=bad).status_code == 422
        bad["rounds"] = "3"
        assert client.post("/api/runs/prepare", json=bad).status_code == 422

        snapshot = client.post("/api/runs/prepare", json=payload()).json()
        run_id = snapshot["run_id"]
        assert snapshot["username"] == "alice b/../"
        assert snapshot["total_turns"] == 6
        assert client.post(f"/api/runs/{run_id}/start").status_code == 200
        assert client.post(f"/api/runs/{run_id}/start").status_code == 409

        for _ in range(200):
            status = client.get(f"/api/runs/{run_id}").json()
            if status["state"] == "finished" and status["storage_status"] != "saving":
                break
            time.sleep(0.05)
        assert status["simulation_status"] == "completed"
        assert status["storage_status"] == "saved"
        assert status["completed_turns"] == 6
        result_id = status["result_id"]
        assert result_id.startswith("alice-b_") and result_id.endswith(run_id)

        listing = client.get("/api/results").json()["results"]
        assert listing[0]["result_id"] == result_id
        doc = client.get(f"/api/results/{result_id}").json()
        assert doc["username"] == "alice b/../"
        assert doc["configuration"] == snapshot["configuration"]
        assert len(doc["transcript"]) == 6
        text = str(doc)
        assert "test-password" not in text and "test-secret" not in text
        assert client.get("/api/results/..%2F..%2Fetc").status_code in (400, 404)


def test_stop_produces_partial_result():
    with make_client() as client:
        client.post("/api/auth/login", json={"username": "bob", "password": "test-password"})
        client.app.state.run_manager._llm = MockLLMClient(delay_seconds=0.2)
        run_id = client.post("/api/runs/prepare", json=payload(rounds=5)).json()["run_id"]
        client.post(f"/api/runs/{run_id}/start")
        time.sleep(0.5)
        assert client.post(f"/api/runs/{run_id}/stop").json()["state"] in ("stopping", "finished")
        for _ in range(100):
            status = client.get(f"/api/runs/{run_id}").json()
            if status["state"] == "finished" and status["storage_status"] != "saving":
                break
            time.sleep(0.05)
        assert status["simulation_status"] == "stopped"
        assert status["storage_status"] == "saved"
        doc = client.get(f"/api/runs/{run_id}/result").json()
        assert doc["status"] == "stopped"
        assert 0 < len(doc["transcript"]) < 15


def test_persona_options_are_enforced():
    with make_client() as client:
        client.post("/api/auth/login", json={"username": "erin", "password": "test-password"})
        schema = client.get("/api/experiment/schema").json()
        fields = {f["name"]: f for f in schema["persona_agent_fields"]}
        assert fields["model"]["options"] == ["openai/gpt-5-nano", "openai/gpt-5.6-luna", "openai/gpt-6-luna"]
        assert fields["model"]["default"] == "openai/gpt-5.6-luna"
        assert fields["nationality"]["widget"] == "combo" and "Japanese" in fields["nationality"]["suggestions"]
        assert fields["ethics"]["generatable"] is True
        assert all(f["generatable"] for f in schema["persona_human_fields"])

        bad = payload()
        bad["agents"][0]["persona_agent"]["model"] = "openai/gpt-4o-mini"
        r = client.post("/api/runs/prepare", json=bad)
        assert r.status_code == 422 and "Model" in r.json()["detail"]
        free = payload()
        free["agents"][0]["persona_agent"]["nationality"] = "Okinawan"  # free typing is allowed
        assert client.post("/api/runs/prepare", json=free).status_code == 200
        assert client.get("/static/js/run/personaEditor.js").headers["cache-control"] == "no-cache"


def test_generate_persona_text_with_mock():
    with make_client() as client:
        client.post("/api/auth/login", json={"username": "erin", "password": "test-password"})
        agent = payload()["agents"][0]["persona_agent"]
        r = client.post("/api/persona/generate", json={"target": "persona_agent", "agent_kind": "ai", "fields": ["ethics"], "persona_agent": agent})
        assert r.status_code == 200, r.text
        assert set(r.json()["values"]) == {"ethics"}
        assert r.json()["model"] == "openai/gpt-6-luna"
        r = client.post("/api/persona/generate", json={"target": "persona_human", "agent_kind": "human", "persona_agent": {"age": ""}})
        assert set(r.json()["values"]) == {"personal_background", "additional_context"}
        # Non-generatable fields are ignored.
        r = client.post("/api/persona/generate", json={"target": "persona_agent", "agent_kind": "ai", "fields": ["age"]})
        assert r.status_code == 502


def wait_finished(client, path, key="state"):
    for _ in range(400):
        status = client.get(path).json()
        if status[key] == "finished" and all(r["storage_status"] != "saving" for r in status.get("runs", [status])):
            return status
        time.sleep(0.05)
    raise AssertionError("did not finish")


def test_scenario_names_scoring_and_legacy_context():
    with make_client() as client:
        client.post("/api/auth/login", json={"username": "fay", "password": "test-password"})
        body = payload(rounds=2)
        body["label"] = "young_voices"
        body["scenario"] = "座談会。課長が若手に質問する。"
        body["initial_message"] = "今日はありがとう。"
        body["human_agent"]["persona_agent"]["name"] = "佐藤課長"
        body["human_agent"]["persona_human"] = {"personal_background": "x", "mental_wellbeing_context": "眠れない"}
        body["agents"][0]["persona_agent"]["name"] = "鈴木"
        snap = client.post("/api/runs/prepare", json=body).json()
        config = snap["configuration"]
        assert config["human_agent"]["name"] == "佐藤課長"
        assert [a["name"] for a in config["agents"]] == ["鈴木", "Agent 2"]
        assert config["human_agent"]["persona_human"]["additional_context"] == "眠れない"
        client.post(f"/api/runs/{snap['run_id']}/start")
        status = wait_finished(client, f"/api/runs/{snap['run_id']}")
        assert status["simulation_status"] == "completed" and status["storage_status"] == "saved"
        doc = client.get(f"/api/runs/{snap['run_id']}/result").json()
        assert doc["schema_version"] == "1.1" and doc["label"] == "young_voices"
        assert status["result_id"].startswith("young_voices--fay_")  # run name starts the filename
        listing = client.get("/api/results").json()["results"]
        assert listing[0]["label"] == "young_voices" and listing[0]["username"] == "fay"
        assert doc["transcript"][0]["content"] == "今日はありがとう。"
        assert doc["transcript"][0]["agent_name"] == "佐藤課長"
        evaluation = doc["evaluation"]
        assert evaluation["status"] == "completed"
        assert [t["round"] for t in evaluation["turns"]] == [1, 2]  # unit = round
        assert set(evaluation["turns"][0]["agents"]) == {"agent_1", "agent_2"}  # per-agent detail
        overall = evaluation["scores"]["overall"]["discounted"]
        assert 0 <= overall <= 1
        assert set(evaluation["scores"]["by_agent"]) == {"agent_1", "agent_2"}
        assert status["score"] == overall
        human = evaluation["scores"]["human_agent"]  # simulator check, separate from overall
        assert list(human["by_round"]) == ["2"]  # round 1 is the fixed initial message
        assert set(human["by_criterion"]) == {"human_realism", "private_state_expression", "agency"}
        assert evaluation["turns"][0]["human"] is None and evaluation["turns"][1]["human"]["score"] is not None
        assert evaluation["turns"][1]["human"]["evidence"] and evaluation["turns"][0]["agents"]["agent_1"]["evidence"]
        assert evaluation["version"] == 3 and evaluation["usage"]["total_tokens"] == 30  # one evaluator call per round

        dup = payload()
        dup["agents"][0]["persona_agent"]["name"] = "X"
        dup["agents"][1]["persona_agent"]["name"] = "X"
        r = client.post("/api/runs/prepare", json=dup)
        assert r.status_code == 400 and "unique" in r.json()["detail"]


def test_batch_runs_sequentially_and_saves_each():
    with make_client() as client:
        client.post("/api/auth/login", json={"username": "gus", "password": "test-password"})
        exps = [payload(rounds=1), payload(rounds=1), payload(rounds=2)]
        snap = client.post("/api/batches/prepare", json={"experiments": exps}).json()
        assert snap["size"] == 3 and snap["total_turns"] == 3 + 3 + 6
        # A second experiment cannot start while the batch runs.
        client.post(f"/api/batches/{snap['batch_id']}/start")
        assert client.post("/api/runs/prepare", json=payload()).status_code == 409
        assert client.get("/api/runs/active").json()["batch"]["batch_id"] == snap["batch_id"]
        status = wait_finished(client, f"/api/batches/{snap['batch_id']}")
        assert [r["simulation_status"] for r in status["runs"]] == ["completed"] * 3
        assert all(r["storage_status"] == "saved" for r in status["runs"])
        listing = client.get("/api/results").json()["results"]
        assert len(listing) == 3
        doc = client.get(f"/api/results/{status['runs'][1]['result_id']}").json()
        assert doc["batch"] == {"batch_id": snap["batch_id"], "index": 2, "size": 3}


def test_batch_stop_skips_remaining_runs():
    with make_client() as client:
        client.post("/api/auth/login", json={"username": "hal", "password": "test-password"})
        client.app.state.run_manager._llm = MockLLMClient(delay_seconds=0.15)
        snap = client.post("/api/batches/prepare", json={"experiments": [payload(rounds=3)] * 3}).json()
        client.post(f"/api/batches/{snap['batch_id']}/start")
        time.sleep(0.4)
        client.post(f"/api/batches/{snap['batch_id']}/stop")
        status = wait_finished(client, f"/api/batches/{snap['batch_id']}")
        assert status["runs"][0]["simulation_status"] == "stopped"
        assert [r["state"] for r in status["runs"][1:]] == ["skipped", "skipped"]


def test_result_names():
    from datetime import datetime, timezone

    from backend.results.naming import build_result_id, parse_result_id

    when = datetime(2026, 10, 5, 8, 9, 12, tzinfo=timezone.utc)
    rid = build_result_id("alice", when, "run_a83f2c", "young voices / no fac")
    assert rid == "young-voices-no-fac--alice_2026-10-05T08-09-12_run_a83f2c"
    assert parse_result_id(rid)["label"] == "young-voices-no-fac" and parse_result_id(rid)["username"] == "alice"
    assert build_result_id("alice", when, "run_a83f2c", "若手の本音") == "alice_2026-10-05T08-09-12_run_a83f2c"
    assert parse_result_id("ren_2026-10-13T15-51-55_run_bb2857")["label"] == ""  # old names still parse
    assert build_result_id("a--b", when, "run_a83f2c", "x") == "x--a-b_2026-10-05T08-09-12_run_a83f2c"
