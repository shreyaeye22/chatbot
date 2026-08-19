from __future__ import annotations

from pydantic_ai.models.test import TestModel

from agents.deps import AgentDeps
from agents.escalation_agent import escalation_agent


def test_escalation_agent_can_call_its_tools_against_a_real_db(seeded_db_path, vector_index_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice", vector_index_path=vector_index_path)

    result = escalation_agent.run_sync(
        "why does my Teams app keep logging me out?", deps=deps, model=TestModel()
    )

    assert isinstance(result.output, str)
    assert result.output
