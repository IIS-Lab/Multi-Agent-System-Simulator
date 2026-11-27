"""Offline stand-in for OpenRouter (LLM_PROVIDER=mock).

Useful for testing the UI and storage flow without spending credits. Runs made
with it record `"llm_provider": "mock"` in their configuration.
"""

from __future__ import annotations

import asyncio
import json
import random
import re

from backend.openrouter.client import Completion


class MockLLMClient:
    def __init__(self, delay_seconds: float = 0.6):
        self._delay = delay_seconds

    async def complete(self, model, messages, temperature, max_tokens, timeout, reasoning_effort=None, json_output=False) -> Completion:
        await asyncio.sleep(self._delay)
        if json_output and re.search(r"^Round: ", messages[-1]["content"], re.MULTILINE):
            # Rubric evaluation request (one round): random ratings for the round, each agent and the human.
            content = messages[-1]["content"]

            def line(label):
                return re.search(rf"^{label}: (.+)$", content, re.MULTILINE).group(1)

            keys = [k.strip() for k in line("Criteria").split(",")]
            names = [n.strip() for n in line("Agents").split(",")]
            human_keys = [k.strip() for k in line("Human criteria").split(",")]
            item = {
                "round": int(line("Round")),
                "scores": {k: random.randint(2, 5) for k in keys},
                "agents": {n: {**{k: random.randint(1, 5) for k in keys}, "evidence": "Mock evidence."} for n in names},
                "human": {**{k: random.randint(1, 5) for k in human_keys}, "evidence": "Mock evidence."} if line("Rate human") == "yes" else None,
                "note": "Mock note.",
            }
            return Completion(content=json.dumps(item), model=model, provider="mock", finish_reason="stop", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, cost=0.0)
        if json_output:
            # Persona generation request: answer with a JSON object for the requested keys.
            match = re.search(r"^Keys: (.+)$", messages[-1]["content"], re.MULTILINE)
            keys = [k.strip() for k in match.group(1).split(",")] if match else []
            text = json.dumps({key: f"(Mock {key.replace('_', ' ')} #{random.randrange(1000)})" for key in keys})
            return Completion(content=text, model=model, provider="mock", finish_reason="stop", cost=0.0)
        last = messages[-1]["content"].splitlines()[-1][:80]
        system = messages[0]["content"]
        speaker = "Human Agent" if "role-playing a human" in system else system.split(",")[0].replace("You are ", "")
        text = f"(Mock reply from {speaker}) Responding to: \"{last}\""
        prompt_tokens = sum(len(m["content"].split()) for m in messages)
        completion_tokens = len(text.split())
        return Completion(
            content=text,
            model=model,
            provider="mock",
            generation_id=f"mock-{random.randrange(16**8):08x}",
            finish_reason="stop",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            cost=0.0,
            latency_ms=int(self._delay * 1000),
        )
