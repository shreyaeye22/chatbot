from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from capabilities.memory.student_memory import record_question
from config.settings import SEED_DIR, SUPPORTED_SUBJECTS
from data.db import ensure_db, get_connection
from data.document_ingest import list_course_content


def test_app_boots_without_exceptions():
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    assert not at.exception


def test_chat_is_blocked_until_the_student_enters_an_api_key():
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    assert at.chat_input[0].disabled
    assert any("API key" in error.value for error in at.main.error)
    assert all(button.disabled for button in at.main.button)  # FAQ prompt shortcuts
    add_notes_button = next(b for b in at.sidebar.button if b.label == "Add to course notes")
    assert add_notes_button.disabled


def test_chat_unblocks_once_an_api_key_is_entered():
    at = AppTest.from_file("src/app.py")
    at.session_state["user_api_key"] = "sk-ant-test-key"
    at.run(timeout=30)

    assert not at.chat_input[0].disabled
    assert len(at.main.error) == 0


def test_teacher_upload_subject_picker_offers_every_supported_subject():
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    subject_picker = at.sidebar.selectbox[0]
    assert subject_picker.options == SUPPORTED_SUBJECTS


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
    at.session_state["focused_content_id"] = focused_id
    at.run(timeout=30)
    assert len(at.main.info) == 1

    at.button(key="clear_focused_file").click().run(timeout=30)

    assert len(at.main.info) == 0
    assert at.session_state["focused_content_id"] is None
