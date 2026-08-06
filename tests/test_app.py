from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from capabilities.memory.student_memory import record_question
from config.settings import SEED_DIR, SUPPORTED_SUBJECTS
from data.db import ensure_db, get_connection


def test_app_boots_without_exceptions():
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    assert not at.exception


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
