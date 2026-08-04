from __future__ import annotations

from pydantic_ai import messages as m
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agents.deps import AgentDeps
from agents.orchestrator import (
    ESCALATION_FALLBACK_REPLY,
    OFF_TOPIC_REPLY,
    _run_agent_safely,
    route_and_answer,
)
from data.db import get_connection


def _scripted_model(route: str, specialist_reply: str) -> FunctionModel:
    """A FunctionModel that answers the orchestrator's routing call with `route`,
    and any specialist agent's call with `specialist_reply`."""

    def _script(messages: list, info: AgentInfo) -> m.ModelResponse:
        if info.output_tools:
            tool_name = info.output_tools[0].name
            return m.ModelResponse(
                parts=[m.ToolCallPart(tool_name=tool_name, args={"route": route, "reason": "test"})]
            )
        return m.ModelResponse(parts=[m.TextPart(content=specialist_reply)])

    return FunctionModel(_script)


def _always_raise(messages: list, info: AgentInfo) -> m.ModelResponse:
    raise RuntimeError("simulated model failure")


def test_off_topic_short_circuits_without_calling_the_model(seeded_db_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    poison_model = FunctionModel(_always_raise)

    answer = route_and_answer("What's your favorite movie?", deps, model=poison_model)

    assert answer.route == "off_topic"
    assert answer.text == OFF_TOPIC_REPLY

    conn = get_connection(seeded_db_path)
    row = conn.execute("SELECT route FROM question_log WHERE student_id = 'alice'").fetchone()
    conn.close()
    assert row["route"] == "off_topic"


def test_routes_to_the_scripted_specialist_and_logs_it(seeded_db_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    model = _scripted_model("concept", "Think about F = m * a. What happens if mass doubles?")

    answer = route_and_answer("why does newton's second law work", deps, model=model)

    assert answer.route == "concept"
    assert answer.text == "Think about F = m * a. What happens if mass doubles?"

    conn = get_connection(seeded_db_path)
    row = conn.execute("SELECT route, answered FROM question_log WHERE student_id = 'alice'").fetchone()
    conn.close()
    assert row["route"] == "concept"
    assert row["answered"] == 1


def test_falls_back_to_escalation_when_the_model_fails(seeded_db_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    poison_model = FunctionModel(_always_raise)

    answer = route_and_answer("when is my math homework due", deps, model=poison_model)

    assert answer.route == "escalation"
    assert answer.text == ESCALATION_FALLBACK_REPLY

    conn = get_connection(seeded_db_path)
    row = conn.execute(
        "SELECT route, answered FROM question_log WHERE student_id = 'alice'"
    ).fetchone()
    conn.close()
    assert row["route"] == "escalation"
    assert row["answered"] == 0


def test_run_agent_safely_returns_error_instead_of_raising(seeded_db_path):
    from agents.logistics_agent import logistics_agent

    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    poison_model = FunctionModel(_always_raise)

    output, new_messages, error = _run_agent_safely(
        logistics_agent, "when is my homework due", deps=deps, model=poison_model, message_history=[]
    )

    assert output is None
    assert new_messages == []
    assert isinstance(error, Exception)
