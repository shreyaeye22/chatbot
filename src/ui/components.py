"""Reusable Streamlit chat rendering, status-indicator, and attachment helpers."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Iterator

import pandas as pd
import streamlit as st
from pydantic_ai import BinaryContent, UserContent

from data.db import SEED_UPLOAD_TIMESTAMP
from data.document_ingest import extract_text

DOCUMENT_EXTENSIONS = ["docx", "pdf", "pptx", "txt", "md"]
IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "webp"]

# Role icon shown in the course library's "Uploaded By" column - falls back to a
# plain document icon for legacy/unrecognized owner values.
ROLE_ICONS = {"Teacher": "🧑‍🏫", "Student": "🎓"}

# Maps an agent-callable tool (toolsets/*) to the underlying skill module that does its
# real work (skills/* or capabilities/*), purely for the status-window trace below - the
# tool is the thing the model chose to call, the skill is what actually ran.
TOOL_SKILLS = {
    "get_upcoming_deadlines": "skills.lookup_deadlines",
    "get_next_deadline": "skills.lookup_deadlines",
    "search_course_content": "capabilities.retrieval.vector_store",
    "check_if_repeated_question": "capabilities.memory.student_memory",
}

ROUTE_LABELS = {
    "logistics": "the logistics helper",
    "concept": "the concept tutor",
    "escalation": "your teacher (escalated)",
    "off_topic": "nowhere (off-topic)",
    "greeting": "nowhere (greeting)",
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


def format_attached_content(name: str, text: str) -> str:
    """Shared "[Attached file 'name':]\ntext" formatting for a document's text,
    whether it's an ad-hoc chat_input attachment or a library-selected course file.
    """
    return f"[Attached file '{name}':]\n{text}"


def build_message_content(
    text: str,
    uploaded_file: Any | None,
    focused_document: dict | None = None,
) -> str | list[UserContent]:
    """Turn a chat message + optional attachment(s) into agent-ready input.

    Images are passed through natively as multimodal content so the model can
    actually see them (vision). Other documents are text-extracted
    (data.document_ingest, same parsers as the teacher-upload path) and folded
    into the prompt as context, since there's no benefit to sending a Word doc
    or PDF as raw bytes when we can already read it deterministically.

    `focused_document`, if given, is a course_content row dict (needs
    `filename` and `content` keys, as returned by
    data.document_ingest.get_course_content_by_id) - the student's
    persistently-attached library selection. Its text folds in the same way
    as `uploaded_file`'s, and composes with an ad-hoc `uploaded_file`
    attachment if both are present on the same turn.
    """
    text_parts = [text] if text else []
    if focused_document is not None:
        text_parts.append(
            format_attached_content(focused_document["filename"], focused_document["content"])
        )

    if uploaded_file is None:
        return "\n\n".join(text_parts) if text_parts else ""

    if uploaded_file.type and uploaded_file.type.startswith("image/"):
        parts: list[UserContent] = []
        combined_text = "\n\n".join(text_parts)
        if combined_text:
            parts.append(combined_text)
        parts.append(BinaryContent(data=uploaded_file.getvalue(), media_type=uploaded_file.type))
        return parts

    extracted = extract_text(uploaded_file, uploaded_file.name)
    text_parts.append(format_attached_content(uploaded_file.name, extracted))
    return "\n\n".join(text_parts)


def render_chat_history(chat_history: list[dict]) -> None:
    for message in chat_history:
        with st.chat_message(message["role"]):
            trace = message.get("trace")
            if trace:
                with st.expander("How I got this answer", expanded=False):
                    render_tool_trace(st, trace["route"], trace["tool_calls"])
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


def render_faq_prompts(prompts: list[str], *, disabled: bool = False) -> str | None:
    """Row of clickable frequently-asked-question buttons next to the chat input.

    `disabled` blocks the buttons (e.g. app.py sets this when the assistant
    isn't ready to answer, such as a missing built-in Hugging Face token)
    since clicking one sends a message straight to the model, same as typing
    it. Returns the clicked prompt's
    text so the caller can feed it through the same send path as a typed
    message, or None if nothing was clicked (including while disabled).
    """
    if not prompts:
        return None

    st.caption("Frequently asked")
    clicked = None
    for col, prompt in zip(st.columns(len(prompts)), prompts):
        with col:
            if st.button(
                prompt, key=f"faq_prompt_{prompt}", use_container_width=True, disabled=disabled
            ):
                clicked = prompt
    return clicked


def format_uploader(owner: str, uploaded_by: str) -> str:
    """Course library "Uploaded By" cell: a role icon plus "<Role>" or, when a
    name was recorded (a real upload rather than seed/legacy data), "<Role> · <name>".
    """
    icon = ROLE_ICONS.get(owner, "📄")
    return f"{icon} {owner} · {uploaded_by}" if uploaded_by else f"{icon} {owner}"


def format_upload_timestamp(created_at: str) -> str:
    """Course library "Uploaded" cell: a friendly rendering of the stored UTC
    `created_at` (data.document_ingest.store_course_content's "%Y-%m-%dT%H:%M:%SZ"
    format), or "—" for seed/legacy rows with no real upload timestamp
    (data.db.SEED_UPLOAD_TIMESTAMP, or an empty value).
    """
    if not created_at or created_at == SEED_UPLOAD_TIMESTAMP:
        return "—"
    try:
        parsed = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return "—"
    return parsed.strftime("%b %d, %Y · %I:%M %p")


def render_course_library(files: list[dict]) -> int | None:
    """Right-side panel: a File/Subject/Uploaded By/Uploaded table of every
    course_content row (newest upload first - data.document_ingest.list_course_content
    orders it that way already), click-to-select. `files` is that function's return
    value. Returns the clicked row's course_content id this run, or None if
    nothing was clicked (caller owns persisting the choice into session_state -
    this function only reports the event, same division of responsibility as
    render_faq_prompts).

    Known, accepted limitation: the table's own row highlight resets on any
    rerun not triggered by clicking this same table (e.g. after sending a chat
    message) even though the underlying selection stays correctly tracked in
    session_state and the badge stays accurate - cosmetic only, not worth
    fighting Streamlit over.
    """
    st.subheader("Course files")
    if not files:
        st.caption("No course files yet.")
        return None

    table = pd.DataFrame(files)
    table["Uploaded By"] = [format_uploader(f["owner"], f["uploaded_by"]) for f in files]
    table["Uploaded"] = [format_upload_timestamp(f["created_at"]) for f in files]
    table = table[["filename", "subject", "Uploaded By", "Uploaded"]].rename(
        columns={"filename": "File", "subject": "Subject"}
    )
    event = st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height=360,
        on_select="rerun",
        selection_mode="single-row",
        key="course_library_table",
        column_config={
            "File": st.column_config.TextColumn("File", width="medium"),
            "Subject": st.column_config.TextColumn("Subject", width="large"),
            "Uploaded By": st.column_config.TextColumn("Uploaded By", width="medium"),
            "Uploaded": st.column_config.TextColumn("Uploaded", width="medium"),
        },
    )
    selected_rows = event.selection.rows if event is not None else []
    if not selected_rows:
        return None
    # Positional index into `files` matches `table`'s row order - only columns
    # are dropped/renamed above, rows are never filtered/reordered.
    return files[selected_rows[0]]["id"]


def render_provider_sidebar() -> str | None:
    """Sidebar box for optionally upgrading from the free Hugging Face model to Claude.

    The assistant runs out of the box on the app's own configured Hugging
    Face model - no key needed from the student. Pasting a legitimate
    Anthropic API key here switches this session to Claude for higher-quality
    answers; the app never uses a built-in Anthropic secret to serve model
    calls (config.settings.with_anthropic_upgrade), so this must be the
    student's own key, and it's used for this browser tab's session only -
    never stored or logged. Bound directly to
    st.session_state["user_anthropic_key"] via `key=` (Streamlit's normal
    widget-state pattern, e.g. upload_subject in app.py), so the value is also
    readable straight from session_state on later reruns. Returns the entered
    key, or None if the box is empty (i.e. stay on Hugging Face).
    """
    st.header("Model")
    st.caption("Running on the free Hugging Face model.")
    with st.expander("Upgrade to Claude (optional)"):
        anthropic_key = st.text_input(
            "Anthropic API key",
            type="password",
            key="user_anthropic_key",
            help="Paste your own legitimate Claude API key to switch this "
            "session to Claude for higher-quality answers. Kept in this "
            "browser tab only - never stored, logged, or sent anywhere but "
            "Anthropic's API.",
        )
    return anthropic_key or None


def render_sign_in_screen() -> tuple[str, str] | None:
    """Sign-in screen shown before any chat content renders: pick a role, type a
    display name, no password. Part of the lightweight, session-based role gate
    (see capabilities.auth.session_auth) - not real authentication.

    Returns (name, lowercased_role) once "Sign In" is clicked with a non-empty
    name, else None (including on first render and while validation fails).
    """
    st.title("🎓 MYP Academic Assistant")
    st.subheader("Sign in to continue")
    role_label = st.radio("I am a...", ["Student", "Teacher"], horizontal=True, key="sign_in_role")
    name = st.text_input("Display name", placeholder="e.g. Alex", key="sign_in_name")
    if st.button("Sign In", type="primary", key="sign_in_button"):
        if not name.strip():
            st.error("Please enter a display name.")
            return None
        return name.strip(), role_label.lower()
    return None


def render_profile_badge(user_name: str, user_role: str | None) -> bool:
    """Top-right avatar (first letter of the signed-in user's name) with a Log
    Out control, shown on every screen once signed in.

    A true CSS-only `:hover` dropdown can't call back into Streamlit's Python
    session (`:hover` is DOM-only), and hand-positioning a real Streamlit
    button under a `position: fixed` overlay is fragile here: Streamlit
    rebuilds the DOM on every rerun, so an overlaid widget can end up
    misaligned or unclickable. st.popover is Streamlit's supported primitive
    for "click a small badge, reveal a mini panel with real widgets" - it's
    used here instead, with CSS only for the badge's own fixed top-right
    position and circular styling (not for revealing the button).

    Returns True the run "Log Out" is clicked.
    """
    st.markdown(
        """
        <style>
        div[data-testid="stPopover"] {
            position: fixed;
            /* Streamlit's own header (Deploy/menu icons) is a `position: absolute`
            bar with z-index 999990 covering the very top of the page - sitting
            below it (rather than fighting it for the same strip) avoids both an
            overlap with those controls and a z-index war. */
            top: 4.5rem;
            right: 1.2rem;
            z-index: 999991;
            /* Without this, the element keeps its normal-flow full width and its
            button ends up left-aligned inside that box - i.e. at the LEFT edge
            of the screen - instead of at the `right` offset above. */
            width: fit-content;
        }
        div[data-testid="stPopover"] button {
            border-radius: 50%;
            width: 2.75rem;
            height: 2.75rem;
            padding: 0;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    initial = (user_name or "?").strip()[:1].upper() or "?"
    with st.popover(initial):
        st.write(f"**{user_name}**")
        if user_role:
            st.caption(user_role.capitalize())
        return st.button("Log Out", key="logout_button", use_container_width=True)


def render_focused_file_badge(focused_file: dict | None) -> bool:
    """Badge + Clear button for a persistently-attached library file, shown
    above the chat input. Returns True if Clear was clicked this run."""
    if focused_file is None:
        return False
    badge_col, clear_col = st.columns([5, 1])
    with badge_col:
        st.info(f"📎 Attached: **{focused_file['filename']}** ({focused_file['subject']})")
    with clear_col:
        return st.button("Clear", key="clear_focused_file")
