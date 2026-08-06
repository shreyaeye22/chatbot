"""Streamlit entrypoint: renders chat UI, wires user input to the orchestrator."""

from __future__ import annotations

import streamlit as st
from pydantic_ai import BinaryContent

from agents.deps import AgentDeps
from agents.orchestrator import route_and_answer
from agents.vision_agent import vision_agent
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
from data.document_ingest import ingest_document, store_course_content
from skills.summarize_common_questions import build_teacher_digest
from ui.components import (
    build_message_content,
    parse_chat_input,
    render_chat_history,
    render_teacher_digest,
    stream_text,
    upload_file_types,
)

st.set_page_config(page_title="MYP Academic Assistant", page_icon="🎓")


@st.cache_resource
def bootstrap() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    ensure_db(DB_PATH, SEED_DIR)


bootstrap()
init_session_state(st.session_state)

settings = load_settings()
# Image transcription (agents/vision_agent.py) needs a vision-capable model; the free
# Hugging Face fallback model isn't one, so images are only offered on Anthropic.
vision_enabled = settings.llm_provider == "anthropic"

deps = AgentDeps(db_path=str(DB_PATH), student_id=DEMO_STUDENT_ID)

with st.sidebar:
    st.header("Teacher tools")

    upload_label = "Upload course material (.docx, .pdf, .pptx, .txt, .md"
    upload_label += ", images)" if vision_enabled else ")"
    with st.expander(upload_label):
        subject = st.selectbox("Subject", SUPPORTED_SUBJECTS, key="upload_subject")
        topic = st.text_input("Topic label", placeholder="e.g. linear equations")
        uploaded = st.file_uploader("File", type=upload_file_types(include_images=vision_enabled))
        if not vision_enabled:
            st.caption("Image upload needs the Anthropic provider (set LLM_PROVIDER=anthropic).")
        if st.button("Add to course notes", disabled=not (uploaded and topic)):
            conn = get_connection(deps.db_path)
            try:
                if uploaded.type and uploaded.type.startswith("image/"):
                    vision_result = vision_agent.run_sync(
                        [BinaryContent(data=uploaded.getvalue(), media_type=uploaded.type)],
                        model=get_model(),
                        model_settings=get_model_settings(),
                    )
                    store_course_content(
                        conn,
                        subject=subject,
                        topic=topic,
                        content=vision_result.output,
                        source_name=uploaded.name,
                    )
                else:
                    ingest_document(
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
st.caption("You can attach a photo or file of a worksheet to your question, too.")

render_chat_history(get_chat_history(st.session_state))

chat_value = st.chat_input(
    "Ask a question...",
    accept_file=True,
    file_type=upload_file_types(include_images=vision_enabled),
)
text, attachment = parse_chat_input(chat_value)

if text or attachment is not None:
    display_text = text or f"[attached {attachment.name}]"
    add_chat_message(st.session_state, "user", display_text)
    with st.chat_message("user"):
        st.write(display_text)
        if attachment is not None and attachment.type and attachment.type.startswith("image/"):
            st.image(attachment.getvalue())

    message_content = build_message_content(text, attachment)

    with st.chat_message("assistant"):
        with st.status("Thinking...", expanded=False) as status:
            status.update(label="Checking your question...")
            model = get_model()
            model_settings = get_model_settings()
            status.update(label="Finding the right helper and looking things up...")
            answer = route_and_answer(
                message_content,
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
