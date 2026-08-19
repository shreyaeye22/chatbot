from __future__ import annotations

from pydantic_ai.models.test import TestModel

from agents.deps import AgentDeps
from agents.logistics_agent import logistics_agent


def test_logistics_agent_can_call_its_tools_against_a_real_db(seeded_db_path, vector_index_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice", vector_index_path=vector_index_path)

    result = logistics_agent.run_sync(
        "what's due this week in math?", deps=deps, model=TestModel()
    )

    assert isinstance(result.output, str)
    assert result.output
