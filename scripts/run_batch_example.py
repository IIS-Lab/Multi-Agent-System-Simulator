"""Example: run the simulation engine directly, without the web UI.

    python -m scripts.run_batch_example            # uses LLM_PROVIDER / OPENROUTER_API_KEY from .env
    LLM_PROVIDER=mock python -m scripts.run_batch_example

Shows how batch experiments can reuse the same engine, result schema and
storage modules as the web app.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from backend.openrouter.client import OpenRouterClient
from backend.openrouter.mock_client import MockLLMClient
from backend.persona.persona_agent import PersonaAgent
from backend.persona.persona_human import PersonaHuman
from backend.results.naming import build_result_id, new_run_id
from backend.results.schema import build_result_document
from backend.runs.config_builder import AIAgentInput, ExperimentRequest, HumanAgentInput, build_run_configuration
from backend.settings import get_settings
from backend.simulation.engine import run_simulation


async def main() -> None:
    settings = get_settings()
    llm = (
        MockLLMClient(delay_seconds=0.05)
        if settings.llm_provider == "mock"
        else OpenRouterClient(settings.openrouter_api_key, settings.openrouter_base_url, settings.app_public_url)
    )

    request = ExperimentRequest(
        rounds=2,
        ordering="randomized",
        human_agent=HumanAgentInput(
            persona_agent=PersonaAgent(age=24, gender="Female", nationality="Japanese"),
            persona_human=PersonaHuman(personal_background="Graduate student living alone."),
        ),
        agents=[AIAgentInput(persona_agent=PersonaAgent()), AIAgentInput(persona_agent=PersonaAgent(age=50))],
    )
    config = build_run_configuration(request, llm_provider=settings.llm_provider)
    result = await run_simulation(config, llm)

    created = datetime.now(timezone.utc)
    run_id = new_run_id()
    document = build_result_document(
        run_id=run_id,
        username="batch_script",
        created_at=created.isoformat(timespec="seconds").replace("+00:00", "Z"),
        configuration=config,
        result=result,
    )
    print(build_result_id("batch_script", created, run_id), result.status, f"{result.completed_turns}/{result.total_turns} turns")
    print(json.dumps(document["transcript"][:2], indent=2))
    # To save: await get_result_storage(settings).save_result(result_id, document)


if __name__ == "__main__":
    asyncio.run(main())
