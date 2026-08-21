from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from capabilities.memory.student_memory import record_question
from config.settings import SEED_DIR, SUPPORTED_SUBJECTS, Settings
from data.db import ensure_db, get_connection
from data.document_ingest import list_course_content

IMAGE_UPGRADE_CAPTION = "Image upload needs the Claude upgrade above."


def _settings(hf_token: str | None = "hf_test_token") -> Settings:
    """A deterministic Settings stand-in so tests don't depend on whatever a
    developer's local .streamlit/secrets.toml happens to contain."""
    return Settings(
        llm_provider="huggingface",
        hf_token=hf_token,
        hf_model_name="meta-llama/Llama-3.2-3B-Instruct",
        anthropic_api_key=None,
        anthropic_model_name="claude-sonnet-5",
        log_level="INFO",
    )


def _sign_in(at: AppTest, name: str, role: str) -> AppTest:
    """Drive the sign-in screen the way a real user would: pick a role, type a
    name, click Sign In. `role` is 'Student' or 'Teacher' (matches the radio's
    displayed label, not the lowercased session_state value)."""
    at.radio(key="sign_in_role").set_value(role).run(timeout=30)
    at.text_input(key="sign_in_name").input(name).run(timeout=30)
    at.button(key="sign_in_button").click().run(timeout=30)
    return at


def _signed_in_state(at: AppTest, *, role: str = "student", name: str = "Test User") -> AppTest:
    """Pre-seed a signed-in session (bypassing the sign-in screen widgets)
    before the first at.run(), for tests that exercise something other than
    the sign-in flow itself - same pattern as other tests here that set
    session_state directly ahead of at.run() (e.g. focused_content_id below)."""
    at.session_state["logged_in"] = True
    at.session_state["user_name"] = name
    at.session_state["user_role"] = role
    return at


def test_app_boots_without_exceptions(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    assert not at.exception


def test_signed_out_visitor_sees_the_sign_in_screen_not_the_chat(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    assert not at.exception
    assert len(at.chat_input) == 0
    assert at.button(key="sign_in_button").label == "Sign In"
    assert at.session_state["logged_in"] is False


def test_signing_in_reveals_the_chat_app_and_stores_the_session(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    _sign_in(at, "Alex", "Student")

    assert not at.exception
    assert len(at.chat_input) == 1
    assert at.session_state["logged_in"] is True
    assert at.session_state["user_name"] == "Alex"
    assert at.session_state["user_role"] == "student"


def test_signing_in_without_a_name_stays_on_the_sign_in_screen(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    at.button(key="sign_in_button").click().run(timeout=30)

    assert not at.exception
    assert len(at.chat_input) == 0
    assert at.session_state["logged_in"] is False
    assert any("display name" in error.value for error in at.main.error)


def test_teacher_tools_are_shown_to_a_teacher_and_hidden_from_a_student(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)

    teacher = AppTest.from_file("src/app.py")
    teacher.run(timeout=30)
    _sign_in(teacher, "Ms. Smith", "Teacher")
    assert "Teacher tools" in [h.value for h in teacher.sidebar.header]

    student = AppTest.from_file("src/app.py")
    student.run(timeout=30)
    _sign_in(student, "Alex", "Student")
    assert "Teacher tools" not in [h.value for h in student.sidebar.header]


def test_logging_out_clears_the_session_and_returns_to_the_sign_in_screen(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)
    _sign_in(at, "Alex", "Student")
    assert len(at.chat_input) == 1

    at.button(key="logout_button").click().run(timeout=30)

    assert not at.exception
    assert len(at.chat_input) == 0
    assert at.button(key="sign_in_button").label == "Sign In"
    assert at.session_state["logged_in"] is False
    assert at.session_state["user_name"] == ""
    assert at.session_state["user_role"] is None


def test_logging_out_preserves_chat_history_for_that_session(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)
    _sign_in(at, "Alex", "Student")
    at.session_state["chat_history"] = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    at.run(timeout=30)

    at.button(key="logout_button").click().run(timeout=30)

    assert at.session_state["chat_history"] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_chat_is_ready_by_default_on_hugging_face_with_no_key(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    _signed_in_state(at)
    at.run(timeout=30)

    assert not at.chat_input[0].disabled
    assert len(at.main.error) == 0
    assert not any(button.disabled for button in at.main.button)  # FAQ prompt shortcuts


def test_chat_is_blocked_when_the_built_in_hugging_face_token_is_missing(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", lambda: _settings(hf_token=None))
    at = AppTest.from_file("src/app.py")
    _signed_in_state(at)
    at.run(timeout=30)

    assert at.chat_input[0].disabled
    assert any("isn't configured" in error.value for error in at.main.error)
    # FAQ prompt shortcuts - excludes the profile badge's Log Out button, which
    # stays enabled regardless of chat readiness.
    faq_buttons = [b for b in at.main.button if b.key != "logout_button"]
    assert all(button.disabled for button in faq_buttons)


def test_chat_upgrades_to_claude_when_a_legitimate_key_is_entered(monkeypatch):
    monkeypatch.setattr("config.settings.load_settings", _settings)
    at = AppTest.from_file("src/app.py")
    # The image-upgrade caption being checked below lives in the teacher-only
    # upload panel.
    _signed_in_state(at, role="teacher")
    at.run(timeout=30)
    assert IMAGE_UPGRADE_CAPTION in [c.value for c in at.sidebar.caption]

    at.session_state["user_anthropic_key"] = "sk-ant-test-key"
    at.run(timeout=30)

    assert not at.chat_input[0].disabled
    assert len(at.main.error) == 0
    assert IMAGE_UPGRADE_CAPTION not in [c.value for c in at.sidebar.caption]


def test_teacher_upload_subject_picker_offers_every_supported_subject():
    at = AppTest.from_file("src/app.py")
    _signed_in_state(at, role="teacher")  # upload panel is teacher-only
    at.run(timeout=30)

    subject_picker = at.sidebar.selectbox[0]
    assert subject_picker.options == SUPPORTED_SUBJECTS


def test_faq_prompts_stay_above_the_chat_history_even_with_existing_messages(
    tmp_path: Path, monkeypatch
):
    db_path = tmp_path / "faq_position_test.db"
    ensure_db(db_path, SEED_DIR)
    conn = get_connection(db_path)
    faq_question = "When is the FAQ position quiz?"
    try:
        record_question(
            conn, student_id="faq-position-test", question=faq_question, route="logistics"
        )
    finally:
        conn.close()
    monkeypatch.setattr("config.settings.DB_PATH", db_path)
    monkeypatch.setattr("config.settings.load_settings", _settings)

    at = AppTest.from_file("src/app.py")
    _signed_in_state(at)
    # Simulate a turn having already happened, since that's the case the FAQ row
    # previously drifted below (it was rendered after render_chat_history, so it
    # kept sliding further down the page as the conversation grew).
    at.session_state["chat_history"] = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    at.run(timeout=30)

    element_order = [type(el).__name__ for el in at.main]
    faq_button_index = next(
        i
        for i, el in enumerate(at.main)
        if type(el).__name__ == "Button" and el.label == faq_question
    )
    first_chat_message_index = element_order.index("ChatMessage")
    assert faq_button_index < first_chat_message_index


def test_faq_prompts_appear_next_to_chat_input_not_in_sidebar(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "faq_test.db"
    ensure_db(db_path, SEED_DIR)
    conn = get_connection(db_path)
    faq_question = "When is the FAQ smoke-test quiz?"
    try:
        record_question(
            conn, student_id="faq-smoke-test", question=faq_question, route="logistics"
        )
    finally:
        conn.close()

    # bootstrap() is cached across the test session, so it won't re-seed this
    # path; ensure_db above already did that. Only DB_PATH needs to point here
    # for the rest of app.py (deps, FAQ lookup) to read from this seeded db.
    monkeypatch.setattr("config.settings.DB_PATH", db_path)

    at = AppTest.from_file("src/app.py")
    _signed_in_state(at)
    at.run(timeout=30)

    main_button_labels = [button.label for button in at.main.button]
    sidebar_button_labels = [button.label for button in at.sidebar.button]
    assert faq_question in main_button_labels
    assert faq_question not in sidebar_button_labels


def test_course_library_panel_renders_in_main_body_with_expected_columns(
    tmp_path: Path, monkeypatch
):
    db_path = tmp_path / "library_test.db"
    ensure_db(db_path, SEED_DIR)
    monkeypatch.setattr("config.settings.DB_PATH", db_path)

    at = AppTest.from_file("src/app.py")
    _signed_in_state(at)
    at.run(timeout=30)

    assert len(at.main.dataframe) == 1
    assert len(at.sidebar.dataframe) == 0
    assert list(at.main.dataframe[0].value.columns) == ["File", "Subject", "Owner"]


def test_selecting_a_library_file_persists_across_a_rerun(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "library_test.db"
    ensure_db(db_path, SEED_DIR)
    conn = get_connection(db_path)
    try:
        focused_id = list_course_content(conn)[0]["id"]
        focused_filename = list_course_content(conn)[0]["filename"]
    finally:
        conn.close()
    monkeypatch.setattr("config.settings.DB_PATH", db_path)

    # streamlit.testing.v1's Dataframe element is a plain read-only Element (no
    # click simulation available), so drive session_state directly to test the
    # *persistence* contract rather than the click itself.
    at = AppTest.from_file("src/app.py")
    _signed_in_state(at)
    at.session_state["focused_content_id"] = focused_id
    at.run(timeout=30)

    assert len(at.main.info) == 1
    assert focused_filename in at.main.info[0].value

    at.run(timeout=30)  # an unrelated rerun shouldn't drop the selection

    assert len(at.main.info) == 1
    assert focused_filename in at.main.info[0].value


def test_clearing_the_focused_file_removes_the_badge(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "library_test.db"
    ensure_db(db_path, SEED_DIR)
    conn = get_connection(db_path)
    try:
        focused_id = list_course_content(conn)[0]["id"]
    finally:
        conn.close()
    monkeypatch.setattr("config.settings.DB_PATH", db_path)

    at = AppTest.from_file("src/app.py")
    _signed_in_state(at)
    at.session_state["focused_content_id"] = focused_id
    at.run(timeout=30)
    assert len(at.main.info) == 1

    at.button(key="clear_focused_file").click().run(timeout=30)

    assert len(at.main.info) == 0
    assert at.session_state["focused_content_id"] is None
