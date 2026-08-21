from __future__ import annotations

import io
from types import SimpleNamespace

from pydantic_ai import BinaryContent

from data.db import SEED_UPLOAD_TIMESTAMP
from ui.components import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    build_message_content,
    chat_input_placeholder,
    format_upload_timestamp,
    format_uploader,
    parse_chat_input,
    render_tool_trace,
    upload_file_types,
)


class _StubStatus:
    """Duck-types the subset of st.status's interface render_tool_trace needs."""

    def __init__(self):
        self.lines: list[str] = []

    def write(self, text: str) -> None:
        self.lines.append(text)


class FakeUploadedFile(io.BytesIO):
    """Duck-types Streamlit's UploadedFile: BytesIO + .name + .type."""

    def __init__(self, data: bytes, name: str, mime_type: str):
        super().__init__(data)
        self.name = name
        self.type = mime_type


def test_upload_file_types_includes_images_only_when_enabled():
    assert upload_file_types(include_images=True) == DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS
    assert upload_file_types(include_images=False) == DOCUMENT_EXTENSIONS


def test_parse_chat_input_handles_none():
    assert parse_chat_input(None) == ("", None)


def test_parse_chat_input_handles_plain_string():
    assert parse_chat_input("when is my homework due?") == ("when is my homework due?", None)


def test_parse_chat_input_handles_chat_input_value_with_file():
    fake_file = FakeUploadedFile(b"data", "worksheet.png", "image/png")
    chat_value = SimpleNamespace(text="what's this?", files=[fake_file])

    text, file = parse_chat_input(chat_value)

    assert text == "what's this?"
    assert file is fake_file


def test_parse_chat_input_handles_chat_input_value_with_no_file():
    chat_value = SimpleNamespace(text="hello", files=[])

    assert parse_chat_input(chat_value) == ("hello", None)


def test_build_message_content_returns_plain_text_without_attachment():
    assert build_message_content("hello", None) == "hello"


def test_build_message_content_returns_multimodal_list_for_image():
    fake_file = FakeUploadedFile(b"fake-bytes", "worksheet.png", "image/png")

    content = build_message_content("what's this?", fake_file)

    assert content[0] == "what's this?"
    assert isinstance(content[1], BinaryContent)
    assert content[1].media_type == "image/png"
    assert content[1].data == b"fake-bytes"


def test_build_message_content_returns_just_the_image_when_no_caption():
    fake_file = FakeUploadedFile(b"fake-bytes", "worksheet.png", "image/png")

    content = build_message_content("", fake_file)

    assert len(content) == 1
    assert isinstance(content[0], BinaryContent)


def test_build_message_content_extracts_text_for_a_document_attachment():
    fake_file = FakeUploadedFile("Newton's second law: F = m * a".encode("utf-8"), "notes.txt", "text/plain")

    content = build_message_content("can you explain this?", fake_file)

    assert "can you explain this?" in content
    assert "notes.txt" in content
    assert "Newton's second law: F = m * a" in content


def test_build_message_content_folds_in_focused_document_when_no_attachment():
    focused = {"filename": "algebra.txt", "subject": "math", "owner": "Teacher", "content": "solve for x"}

    content = build_message_content("what does this mean?", None, focused)

    assert "what does this mean?" in content
    assert "algebra.txt" in content
    assert "solve for x" in content


def test_build_message_content_folds_in_focused_document_with_no_typed_text():
    focused = {"filename": "algebra.txt", "subject": "math", "owner": "Teacher", "content": "solve for x"}

    content = build_message_content("", None, focused)

    assert content.startswith("[Attached file 'algebra.txt':]")


def test_build_message_content_composes_focused_document_and_ad_hoc_document_attachment():
    focused = {"filename": "algebra.txt", "subject": "math", "owner": "Teacher", "content": "solve for x"}
    fake_file = FakeUploadedFile("extra homework notes".encode("utf-8"), "hw.txt", "text/plain")

    content = build_message_content("compare these", fake_file, focused)

    assert "compare these" in content
    assert "algebra.txt" in content
    assert "solve for x" in content
    assert "hw.txt" in content
    assert "extra homework notes" in content


def test_build_message_content_composes_focused_document_and_image_attachment():
    focused = {"filename": "algebra.txt", "subject": "math", "owner": "Teacher", "content": "solve for x"}
    fake_file = FakeUploadedFile(b"fake-bytes", "worksheet.png", "image/png")

    content = build_message_content("what's this?", fake_file, focused)

    assert "what's this?" in content[0]
    assert "algebra.txt" in content[0]
    assert "solve for x" in content[0]
    assert isinstance(content[1], BinaryContent)


def test_render_tool_trace_lists_each_tool_call_and_its_backing_skill():
    status = _StubStatus()

    render_tool_trace(
        status, "logistics", [{"tool": "get_upcoming_deadlines", "args": {"subject": "math"}}]
    )

    assert any("Routed to" in line for line in status.lines)
    tool_line = next(line for line in status.lines if "get_upcoming_deadlines" in line)
    assert "subject='math'" in tool_line
    assert "skills.lookup_deadlines" in tool_line


def test_render_tool_trace_notes_when_no_tools_were_called():
    status = _StubStatus()

    render_tool_trace(status, "escalation", [])

    assert any("No tools called" in line for line in status.lines)


def test_format_uploader_includes_name_when_present():
    assert format_uploader("Teacher", "Ms. Smith") == "🧑‍🏫 Teacher · Ms. Smith"


def test_format_uploader_falls_back_to_role_only_when_no_name_recorded():
    assert format_uploader("Teacher", "") == "🧑‍🏫 Teacher"


def test_format_uploader_uses_the_student_icon_for_a_student_upload():
    assert format_uploader("Student", "Sam") == "🎓 Student · Sam"


def test_format_uploader_falls_back_to_a_generic_icon_for_an_unrecognized_role():
    assert format_uploader("Admin", "Jo") == "📄 Admin · Jo"


def test_format_upload_timestamp_formats_a_stored_iso_timestamp():
    assert format_upload_timestamp("2026-08-21T15:04:05Z") == "Aug 21, 2026 · 03:04 PM"


def test_format_upload_timestamp_shows_a_placeholder_for_the_seed_sentinel():
    assert format_upload_timestamp(SEED_UPLOAD_TIMESTAMP) == "—"


def test_format_upload_timestamp_shows_a_placeholder_for_an_empty_value():
    assert format_upload_timestamp("") == "—"


def test_chat_input_placeholder_switches_to_a_follow_up_after_the_first_turn():
    assert chat_input_placeholder(has_history=False) == "Ask a question..."
    assert chat_input_placeholder(has_history=True) == "Ask a follow-up question..."
