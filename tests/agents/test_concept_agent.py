from __future__ import annotations

from pydantic_ai.models.test import TestModel

from agents.concept_agent import concept_agent
from agents.deps import AgentDeps


def test_concept_agent_can_call_its_tools_against_a_real_db(seeded_db_path, seeded_index_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice", vector_index_path=seeded_index_path)

    result = concept_agent.run_sync(
        "can you explain newton's second law?", deps=deps, model=TestModel()
    )

    assert isinstance(result.output, str)
    assert result.output
