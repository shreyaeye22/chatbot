from __future__ import annotations

from toolsets.guardrail_tools import check_concept_answer, check_input_message


def test_check_input_message_delegates_to_capability():
    result = check_input_message("What's your favorite movie?")
    assert result.off_topic is True


def test_check_concept_answer_delegates_to_capability():
    result = check_concept_answer("x = 42")
    assert result.too_direct is True


def test_check_input_message_flags_greetings():
    result = check_input_message("Hi there")
    assert result.is_greeting is True
    assert result.off_topic is False
