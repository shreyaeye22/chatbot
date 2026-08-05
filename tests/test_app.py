from __future__ import annotations

from streamlit.testing.v1 import AppTest

from config.settings import SUPPORTED_SUBJECTS


def test_app_boots_without_exceptions():
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    assert not at.exception


def test_teacher_upload_subject_picker_offers_every_supported_subject():
    at = AppTest.from_file("src/app.py")
    at.run(timeout=30)

    subject_picker = at.sidebar.selectbox[0]
    assert subject_picker.options == SUPPORTED_SUBJECTS
