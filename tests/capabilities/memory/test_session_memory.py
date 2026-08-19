from __future__ import annotations

from capabilities.memory.session_memory import (
    add_chat_message,
    get_chat_history,
    get_focused_content_id,
    get_model_message_history,
    init_session_state,
    set_focused_content_id,
    set_model_message_history,
)


def test_chat_history_round_trips_through_session_state():
    session_state: dict = {}
    init_session_state(session_state)

    add_chat_message(session_state, "user", "when is my homework due?")
    add_chat_message(session_state, "assistant", "your math homework is due Thursday.")

    history = get_chat_history(session_state)
    assert history == [
        {"role": "user", "content": "when is my homework due?"},
        {"role": "assistant", "content": "your math homework is due Thursday."},
    ]


def test_chat_message_trace_is_stored_only_when_given():
    session_state: dict = {}
    init_session_state(session_state)

    add_chat_message(session_state, "user", "when is my homework due?")
    add_chat_message(
        session_state,
        "assistant",
        "Thursday.",
        trace={"route": "logistics", "tool_calls": [{"tool": "get_next_deadline", "args": {}}]},
    )

    history = get_chat_history(session_state)
    assert "trace" not in history[0]
    assert history[1]["trace"] == {
        "route": "logistics",
        "tool_calls": [{"tool": "get_next_deadline", "args": {}}],
    }


def test_model_message_history_round_trips_through_session_state():
    session_state: dict = {}
    init_session_state(session_state)

    assert get_model_message_history(session_state) == []

    set_model_message_history(session_state, ["fake-message-1", "fake-message-2"])

    assert get_model_message_history(session_state) == ["fake-message-1", "fake-message-2"]


def test_init_session_state_does_not_clobber_existing_history():
    session_state = {"chat_history": [{"role": "user", "content": "already here"}]}

    init_session_state(session_state)

    assert get_chat_history(session_state) == [{"role": "user", "content": "already here"}]


def test_focused_content_id_round_trips_through_session_state():
    session_state: dict = {}
    init_session_state(session_state)

    assert get_focused_content_id(session_state) is None

    set_focused_content_id(session_state, 3)

    assert get_focused_content_id(session_state) == 3

    set_focused_content_id(session_state, None)

    assert get_focused_content_id(session_state) is None


def test_init_session_state_does_not_clobber_existing_focused_content_id():
    session_state = {"focused_content_id": 7}

    init_session_state(session_state)

    assert get_focused_content_id(session_state) == 7
