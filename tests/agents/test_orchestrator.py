from __future__ import annotations

from pydantic_ai import BinaryContent
from pydantic_ai import messages as m
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agents.deps import AgentDeps
from agents.orchestrator import (
    ESCALATION_FALLBACK_REPLY,
    OFF_TOPIC_REPLY,
    _has_attachment,
    _message_text,
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


def _scripted_tool_call_model(route: str, tool_name: str, final_reply: str) -> FunctionModel:
    """Routes like `_scripted_model`, but has the specialist call `tool_name` once
    (with no args) before answering, so tests can assert on `AgentAnswer.tool_calls`."""

    def _script(messages: list, info: AgentInfo) -> m.ModelResponse:
        if info.output_tools:
            tool_name_ = info.output_tools[0].name
            return m.ModelResponse(
                parts=[m.ToolCallPart(tool_name=tool_name_, args={"route": route, "reason": "test"})]
            )
        already_called = any(
            isinstance(part, m.ToolReturnPart) for msg in messages for part in getattr(msg, "parts", [])
        )
        if already_called:
            return m.ModelResponse(parts=[m.TextPart(content=final_reply)])
        return m.ModelResponse(parts=[m.ToolCallPart(tool_name=tool_name, args={})])

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

    output, new_messages, usage, error = _run_agent_safely(
        logistics_agent, "when is my homework due", deps=deps, model=poison_model, message_history=[]
    )

    assert output is None
    assert new_messages == []
    assert usage is None
    assert isinstance(error, Exception)


def test_message_text_joins_only_the_text_parts():
    image = BinaryContent(data=b"fake", media_type="image/png")
    assert _message_text(["look at this", image]) == "look at this"
    assert _message_text("plain string") == "plain string"
    assert _message_text([image]) == ""


def test_has_attachment_detects_non_text_parts():
    image = BinaryContent(data=b"fake", media_type="image/png")
    assert _has_attachment(["caption", image]) is True
    assert _has_attachment(["just text"]) is False
    assert _has_attachment("plain string") is False


def test_attachment_bypasses_off_topic_check_even_with_an_unrelated_caption(seeded_db_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    model = _scripted_model("concept", "That's a population pyramid - here's a hint...")
    image = BinaryContent(data=b"fake-worksheet-photo", media_type="image/png")

    # "look at this" alone (no subject keyword) would normally be flagged off-topic.
    answer = route_and_answer(["look at this", image], deps, model=model)

    assert answer.route == "concept"
    assert answer.text == "That's a population pyramid - here's a hint..."


def test_image_only_message_logs_a_placeholder_instead_of_crashing(seeded_db_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    model = _scripted_model("concept", "Here's what I see in your photo...")
    image = BinaryContent(data=b"fake-worksheet-photo", media_type="image/png")

    answer = route_and_answer([image], deps, model=model)

    assert answer.route == "concept"

    conn = get_connection(seeded_db_path)
    row = conn.execute("SELECT question FROM question_log WHERE student_id = 'alice'").fetchone()
    conn.close()
    assert row["question"] == "[attached file]"


def test_tool_calls_made_by_the_specialist_are_captured(seeded_db_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    model = _scripted_tool_call_model("logistics", "get_today", "Nothing due today.")

    answer = route_and_answer("what's due today", deps, model=model)

    assert answer.route == "logistics"
    assert answer.tool_calls == [{"tool": "get_today", "args": {}}]


def test_tool_calls_are_empty_when_the_specialist_answers_directly(seeded_db_path):
    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")
    model = _scripted_model("concept", "Think about F = m * a.")

    answer = route_and_answer("why does newton's second law work", deps, model=model)

    assert answer.tool_calls == []


def test_run_agent_safely_returns_usage_on_success(seeded_db_path):
    from agents.logistics_agent import logistics_agent

    deps = AgentDeps(db_path=seeded_db_path, student_id="alice")

    def _reply(messages: list, info: AgentInfo) -> m.ModelResponse:
        return m.ModelResponse(parts=[m.TextPart(content="Your homework is due Friday.")])

    output, _, usage, error = _run_agent_safely(
        logistics_agent,
        "when is my homework due",
        deps=deps,
        model=FunctionModel(_reply),
        message_history=[],
    )

    assert error is None
    assert output == "Your homework is due Friday."
    assert usage is not None
    assert usage.requests == 1
