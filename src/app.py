"""Streamlit entrypoint: renders chat UI, wires user input to the orchestrator."""

from __future__ import annotations

import streamlit as st
from pydantic_ai import BinaryContent

from agents.deps import AgentDeps
from agents.orchestrator import route_and_answer
from agents.vision_agent import vision_agent
from capabilities.auth.session_auth import (
    get_user_name,
    get_user_role,
    init_auth_state,
    is_logged_in,
    log_in,
    log_out,
)
from capabilities.memory.session_memory import (
    add_chat_message,
    get_chat_history,
    get_focused_content_id,
    get_model_message_history,
    init_session_state,
    set_focused_content_id,
    set_model_message_history,
)
from capabilities.observability.logging_setup import setup_logging
from capabilities.retrieval import vector_store
from capabilities.retrieval.vector_store import ensure_index
from config.settings import (
    DB_PATH,
    DEMO_STUDENT_ID,
    SEED_DIR,
    SUPPORTED_SUBJECTS,
    VECTOR_INDEX_PATH,
    get_model,
    get_model_settings,
    load_settings,
    with_anthropic_upgrade,
)
from data.db import ensure_db, get_connection
from data.document_ingest import (
    get_course_content_by_id,
    ingest_document,
    list_course_content,
    store_course_content,
)
from skills.summarize_common_questions import build_faq_prompts
from ui.components import (
    build_message_content,
    chat_input_placeholder,
    parse_chat_input,
    render_chat_history,
    render_course_library,
    render_faq_prompts,
    render_focused_file_badge,
    render_profile_badge,
    render_provider_sidebar,
    render_sign_in_screen,
    render_tool_trace,
    stream_text,
    upload_file_types,
)

st.set_page_config(page_title="MYP Academic Assistant", page_icon="🎓")

# --- Sign-in gate -------------------------------------------------------------
# Lightweight, session-based role gate for UX/testing purposes only - NOT secure
# authentication (no password, no account store, no server-side identity check;
# see capabilities.auth.session_auth and README's "Sign-in" section). Runs before
# anything else so a signed-out visitor never sees chat content, uploads, or the
# course library, and before init_session_state so chat state only gets set up
# once someone's actually signed in.
init_auth_state(st.session_state)

if not is_logged_in(st.session_state):
    sign_in_result = render_sign_in_screen()
    if sign_in_result is not None:
        log_in(st.session_state, *sign_in_result)
        st.rerun()
    st.stop()

if render_profile_badge(get_user_name(st.session_state), get_user_role(st.session_state)):
    log_out(st.session_state)
    st.rerun()
# -------------------------------------------------------------------------------


@st.cache_resource
def bootstrap() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    ensure_db(DB_PATH, SEED_DIR)
    ensure_index(VECTOR_INDEX_PATH, DB_PATH)


bootstrap()
init_session_state(st.session_state)

settings = load_settings()

deps = AgentDeps(
    db_path=str(DB_PATH), student_id=DEMO_STUDENT_ID, vector_index_path=str(VECTOR_INDEX_PATH)
)

with st.sidebar:
    user_anthropic_key = render_provider_sidebar()
    effective_settings = with_anthropic_upgrade(settings, user_anthropic_key)
    # Image transcription (agents/vision_agent.py) needs a vision-capable model; the free
    # Hugging Face model isn't one, so images are only offered once upgraded to Claude.
    vision_enabled = effective_settings.llm_provider == "anthropic"
    # The Hugging Face path runs on the app's own built-in HF_TOKEN, no student key needed;
    # if that secret isn't configured, chat can't work at all until Claude is set up instead.
    chat_ready = vision_enabled or bool(effective_settings.hf_token)

    # Role-gated: only shown to a teacher-signed-in session (capabilities.auth.session_auth).
    if get_user_role(st.session_state) == "teacher":
        st.header("Teacher tools")

        upload_label = "Upload course material (.docx, .pdf, .pptx, .txt, .md"
        upload_label += ", images)" if vision_enabled else ")"
        with st.expander(upload_label):
            subject = st.selectbox("Subject", SUPPORTED_SUBJECTS, key="upload_subject")
            topic = st.text_input("Topic label", placeholder="e.g. linear equations")
            uploaded = st.file_uploader(
                "File", type=upload_file_types(include_images=vision_enabled)
            )
            if not vision_enabled:
                st.caption("Image upload needs the Claude upgrade above.")
            is_image_upload = bool(
                uploaded and uploaded.type and uploaded.type.startswith("image/")
            )
            if is_image_upload and not vision_enabled:
                st.caption("Transcribing a photo needs the Claude upgrade above.")
            if st.button(
                "Add to course notes",
                disabled=not (uploaded and topic) or (is_image_upload and not vision_enabled),
            ):
                conn = get_connection(deps.db_path)
                collection = vector_store.get_collection(deps.vector_index_path)
                try:
                    if is_image_upload:
                        vision_result = vision_agent.run_sync(
                            [BinaryContent(data=uploaded.getvalue(), media_type=uploaded.type)],
                            model=get_model(effective_settings),
                            model_settings=get_model_settings(effective_settings),
                        )
                        store_course_content(
                            conn,
                            subject=subject,
                            topic=topic,
                            content=vision_result.output,
                            source_name=uploaded.name,
                            collection=collection,
                        )
                    else:
                        ingest_document(
                            conn,
                            file=uploaded,
                            subject=subject,
                            topic=topic,
                            source_name=uploaded.name,
                            collection=collection,
                        )
                    st.success(f"Added '{uploaded.name}' to {subject} notes.")
                except ValueError as exc:
                    st.error(str(exc))
                finally:
                    conn.close()

st.title("🎓 MYP Academic Assistant")
st.caption("Ask about homework deadlines, assessment dates, instructions, or a concept from class.")
st.caption("You can attach a photo or file of a worksheet to your question, too.")

chat_col, library_col = st.columns([3, 1], gap="large")

with library_col:
    conn = get_connection(deps.db_path)
    try:
        library_files = list_course_content(conn)
    finally:
        conn.close()
    clicked_id = render_course_library(library_files)
    if clicked_id is not None:
        set_focused_content_id(st.session_state, clicked_id)
        st.rerun()

with chat_col:
    if not chat_ready:
        st.error(
            "⚠️ The assistant isn't configured yet - no Hugging Face token is set up. "
            "Ask your teacher/admin, or upgrade to Claude in the sidebar."
        )

    # Rendered above the chat history (rather than down by the chat input) so it stays put
    # in a fixed spot at the top of the page instead of drifting further down as the
    # conversation grows underneath it.
    conn = get_connection(deps.db_path)
    try:
        faq_prompts = build_faq_prompts(conn, limit=5)
    finally:
        conn.close()
    faq_selection = render_faq_prompts(faq_prompts, disabled=not chat_ready)

    render_chat_history(get_chat_history(st.session_state))

    focused_content_id = get_focused_content_id(st.session_state)
    focused_document = None
    if focused_content_id is not None:
        conn = get_connection(deps.db_path)
        try:
            focused_document = get_course_content_by_id(conn, focused_content_id)
        finally:
            conn.close()
        if focused_document is None:
            set_focused_content_id(st.session_state, None)  # stale id, defensive

    if render_focused_file_badge(focused_document):
        set_focused_content_id(st.session_state, None)
        st.rerun()

    chat_value = st.chat_input(
        chat_input_placeholder(has_history=bool(get_chat_history(st.session_state))),
        accept_file=True,
        file_type=upload_file_types(include_images=vision_enabled),
        disabled=not chat_ready,
    )
    text, attachment = parse_chat_input(chat_value)
    if faq_selection:
        text, attachment = faq_selection, None

    if (text or attachment is not None) and chat_ready:
        display_text = text or f"[attached {attachment.name}]"
        add_chat_message(st.session_state, "user", display_text)
        with st.chat_message("user"):
            st.write(display_text)
            if attachment is not None and attachment.type and attachment.type.startswith("image/"):
                st.image(attachment.getvalue())

        message_content = build_message_content(text, attachment, focused_document)

        with st.chat_message("assistant"):
            with st.status("Thinking...", expanded=False) as status:
                status.update(label="Checking your question...")
                model = get_model(effective_settings)
                model_settings = get_model_settings(effective_settings)
                status.update(label="Finding the right helper and looking things up...")
                answer = route_and_answer(
                    message_content,
                    deps,
                    message_history=get_model_message_history(st.session_state),
                    model=model,
                    model_settings=model_settings,
                )
                render_tool_trace(status, answer.route, answer.tool_calls)
                status.update(label="Done", state="complete")

            st.write_stream(stream_text(answer.text))

        add_chat_message(
            st.session_state,
            "assistant",
            answer.text,
            trace={"route": answer.route, "tool_calls": answer.tool_calls},
        )
        set_model_message_history(
            st.session_state, get_model_message_history(st.session_state) + answer.new_messages
        )
        # Rerun so the chat input immediately reflects updated history (follow-up placeholder,
        # ui.components.chat_input_placeholder) instead of waiting for the next interaction.
        st.rerun()
