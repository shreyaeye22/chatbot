"""Streamlit entrypoint: renders chat UI, wires user input to the orchestrator."""

from __future__ import annotations

import streamlit as st

from agents.deps import AgentDeps
from agents.orchestrator import route_and_answer
from capabilities.memory.session_memory import (
    add_chat_message,
    get_chat_history,
    get_model_message_history,
    init_session_state,
    set_model_message_history,
)
from capabilities.observability.logging_setup import setup_logging
from config.settings import (
    DB_PATH,
    DEMO_STUDENT_ID,
    SEED_DIR,
    SUPPORTED_SUBJECTS,
    get_model,
    get_model_settings,
    load_settings,
)
from data.db import ensure_db, get_connection
from data.ingest_docx import ingest_docx
from skills.summarize_common_questions import build_teacher_digest
from ui.components import render_chat_history, render_teacher_digest, stream_text

st.set_page_config(page_title="MYP Academic Assistant", page_icon="🎓")


@st.cache_resource
def bootstrap() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    ensure_db(DB_PATH, SEED_DIR)


bootstrap()
init_session_state(st.session_state)

deps = AgentDeps(db_path=str(DB_PATH), student_id=DEMO_STUDENT_ID)

with st.sidebar:
    st.header("Teacher tools")

    with st.expander("Upload a worksheet (.docx)"):
        subject = st.selectbox("Subject", SUPPORTED_SUBJECTS)
        topic = st.text_input("Topic label", placeholder="e.g. linear equations")
        uploaded = st.file_uploader("Worksheet", type=["docx"])
        if st.button("Add to course notes", disabled=not (uploaded and topic)):
            conn = get_connection(deps.db_path)
            try:
                ingest_docx(
                    conn,
                    file=uploaded,
                    subject=subject,
                    topic=topic,
                    source_name=uploaded.name,
                )
                st.success(f"Added '{uploaded.name}' to {subject} notes.")
            except ValueError as exc:
                st.error(str(exc))
            finally:
                conn.close()

    with st.expander("Most common student questions", expanded=True):
        conn = get_connection(deps.db_path)
        try:
            digest = build_teacher_digest(conn)
        finally:
            conn.close()
        render_teacher_digest(digest)

st.title("🎓 MYP Academic Assistant")
st.caption("Ask about homework deadlines, assessment dates, instructions, or a concept from class.")

render_chat_history(get_chat_history(st.session_state))

user_message = st.chat_input("Ask a question...")
if user_message:
    add_chat_message(st.session_state, "user", user_message)
    with st.chat_message("user"):
        st.write(user_message)

    with st.chat_message("assistant"):
        with st.status("Thinking...", expanded=False) as status:
            status.update(label="Checking your question...")
            model = get_model()
            model_settings = get_model_settings()
            status.update(label="Finding the right helper and looking things up...")
            answer = route_and_answer(
                user_message,
                deps,
                message_history=get_model_message_history(st.session_state),
                model=model,
                model_settings=model_settings,
            )
            status.update(label="Done", state="complete")

        st.write_stream(stream_text(answer.text))

    add_chat_message(st.session_state, "assistant", answer.text)
    set_model_message_history(
        st.session_state, get_model_message_history(st.session_state) + answer.new_messages
    )
