"""Reusable Streamlit chat rendering and status-indicator helpers."""

from __future__ import annotations

import time
from typing import Iterator

import streamlit as st


def render_chat_history(chat_history: list[dict]) -> None:
    for message in chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])


def stream_text(text: str, delay: float = 0.015) -> Iterator[str]:
    """Yield `text` word-by-word for st.write_stream.

    The orchestrator needs the full answer before it can run the output
    guardrail and log the question, so this is a simulated live-typing
    reveal of the final answer rather than true token-level streaming from
    the model. See ARCHITECTURE.md.
    """
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(delay)


def render_teacher_digest(digest: list[dict]) -> None:
    if not digest:
        st.caption("No repeated questions logged yet.")
        return
    for item in digest:
        st.markdown(f"- {item['summary']}")
