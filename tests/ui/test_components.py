from __future__ import annotations

import io
from types import SimpleNamespace

from pydantic_ai import BinaryContent

from ui.components import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    build_message_content,
    chat_input_placeholder,
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


def test_chat_input_placeholder_switches_to_a_follow_up_after_the_first_turn():
    assert chat_input_placeholder(has_history=False) == "Ask a question..."
    assert chat_input_placeholder(has_history=True) == "Ask a follow-up question..."
