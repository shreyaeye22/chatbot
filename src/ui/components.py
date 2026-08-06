"""Reusable Streamlit chat rendering, status-indicator, and attachment helpers."""

from __future__ import annotations

import time
from typing import Any, Iterator

import streamlit as st
from pydantic_ai import BinaryContent, UserContent

from data.document_ingest import extract_text

DOCUMENT_EXTENSIONS = ["docx", "pdf", "pptx", "txt", "md"]
IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "webp"]

# Maps an agent-callable tool (toolsets/*) to the underlying skill module that does its
# real work (skills/* or capabilities/*), purely for the status-window trace below - the
# tool is the thing the model chose to call, the skill is what actually ran.
TOOL_SKILLS = {
    "get_upcoming_deadlines": "skills.lookup_deadlines",
    "get_next_deadline": "skills.lookup_deadlines",
    "search_course_content": "skills.explain_concept",
    "check_if_repeated_question": "capabilities.memory.student_memory",
}

ROUTE_LABELS = {
    "logistics": "the logistics helper",
    "concept": "the concept tutor",
    "escalation": "your teacher (escalated)",
    "off_topic": "nowhere (off-topic)",
}


def upload_file_types(*, include_images: bool) -> list[str]:
    """Extensions to pass to a file_uploader/chat_input's file_type/type argument.

    Images are only offered when `include_images` is True - the vision path
    (agents/vision_agent.py) requires the Anthropic provider, so app.py gates
    this on the configured LLM_PROVIDER.
    """
    return DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS if include_images else DOCUMENT_EXTENSIONS


def parse_chat_input(user_input: Any) -> tuple[str, Any | None]:
    """Normalize st.chat_input's return value into (text, first_uploaded_file_or_None).

    With accept_file=True, st.chat_input returns a dict-like ChatInputValue
    (`.text`, `.files`) instead of a plain string; this hides that shape from
    the rest of the app.
    """
    if user_input is None:
        return "", None
    if isinstance(user_input, str):
        return user_input, None
    files = user_input.files or []
    return user_input.text, (files[0] if files else None)


def build_message_content(text: str, uploaded_file: Any | None) -> str | list[UserContent]:
    """Turn a chat message + optional attachment into agent-ready input.

    Images are passed through natively as multimodal content so the model can
    actually see them (vision). Other documents are text-extracted
    (data.document_ingest, same parsers as the teacher-upload path) and folded
    into the prompt as context, since there's no benefit to sending a Word doc
    or PDF as raw bytes when we can already read it deterministically.
    """
    if uploaded_file is None:
        return text

    if uploaded_file.type and uploaded_file.type.startswith("image/"):
        parts: list[UserContent] = []
        if text:
            parts.append(text)
        parts.append(BinaryContent(data=uploaded_file.getvalue(), media_type=uploaded_file.type))
        return parts

    extracted = extract_text(uploaded_file, uploaded_file.name)
    label = f"[Attached file '{uploaded_file.name}':]\n{extracted}"
    return f"{text}\n\n{label}" if text else label


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


def render_tool_trace(status: Any, route: str, tool_calls: list[dict]) -> None:
    """Write what actually happened this turn into an st.status container.

    `status` just needs a `.write(str)` method (an `st.status`/`st.container` in the app,
    a stub in tests) so this stays testable without a live Streamlit session. Content
    written here persists in the collapsed status widget after it completes, so expanding
    it later shows which tools/skills the assistant used to answer.
    """
    status.write(f"Routed to {ROUTE_LABELS.get(route, route)}")
    if not tool_calls:
        status.write("No tools called - answered directly.")
        return
    for call in tool_calls:
        args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
        line = f"🔧 Called `{call['tool']}({args})`"
        skill = TOOL_SKILLS.get(call["tool"])
        if skill:
            line += f" → `{skill}`"
        status.write(line)


def chat_input_placeholder(has_history: bool) -> str:
    """Placeholder text for the chat input: nudge toward a follow-up once a turn has happened."""
    return "Ask a follow-up question..." if has_history else "Ask a question..."


def render_faq_prompts(prompts: list[str]) -> str | None:
    """Row of clickable frequently-asked-question buttons next to the chat input.

    Returns the clicked prompt's text so the caller can feed it through the
    same send path as a typed message, or None if nothing was clicked.
    """
    if not prompts:
        return None

    st.caption("Frequently asked")
    clicked = None
    for col, prompt in zip(st.columns(len(prompts)), prompts):
        with col:
            if st.button(prompt, key=f"faq_prompt_{prompt}", use_container_width=True):
                clicked = prompt
    return clicked
