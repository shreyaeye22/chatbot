"""Short-term (session) memory: lives in st.session_state, gone when the tab closes.

Takes a plain MutableMapping rather than importing streamlit directly, so
this logic is testable with an ordinary dict (st.session_state behaves like
one) without needing Streamlit installed/running in tests.
"""

from __future__ import annotations

from typing import Any, MutableMapping

CHAT_HISTORY_KEY = "chat_history"
MODEL_MESSAGE_HISTORY_KEY = "model_message_history"


def init_session_state(session_state: MutableMapping[str, Any]) -> None:
    session_state.setdefault(CHAT_HISTORY_KEY, [])
    session_state.setdefault(MODEL_MESSAGE_HISTORY_KEY, [])


def get_chat_history(session_state: MutableMapping[str, Any]) -> list[dict]:
    """Return the UI-facing history: a list of {role, content} dicts."""
    return session_state.get(CHAT_HISTORY_KEY, [])


def add_chat_message(
    session_state: MutableMapping[str, Any],
    role: str,
    content: str,
    trace: dict | None = None,
) -> None:
    """Append a chat message. `trace` (route + tool_calls) is optional and assistant-only -
    when present it's replayed as a collapsible expander by ui.components.render_chat_history."""
    message: dict[str, Any] = {"role": role, "content": content}
    if trace is not None:
        message["trace"] = trace
    session_state.setdefault(CHAT_HISTORY_KEY, []).append(message)


def get_model_message_history(session_state: MutableMapping[str, Any]) -> list:
    """Return pydantic-ai's ModelMessage history, used to give an agent run conversational context."""
    return session_state.get(MODEL_MESSAGE_HISTORY_KEY, [])


def set_model_message_history(session_state: MutableMapping[str, Any], messages: list) -> None:
    session_state[MODEL_MESSAGE_HISTORY_KEY] = messages
