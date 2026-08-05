from __future__ import annotations

import pytest

from capabilities.guardrails.input_guardrails import check_input


def test_subject_question_is_not_off_topic():
    result = check_input("Can you explain how photosynthesis works?")
    assert result.off_topic is False


def test_logistics_question_is_not_off_topic():
    result = check_input("When is my chemistry homework due?")
    assert result.off_topic is False


@pytest.mark.parametrize(
    "message",
    [
        "When is my French homework due?",
        "Can you help me with my Arabic conjugation?",
        "What's due this week in Individuals and Societies?",
        "Can you explain how to read a population pyramid in Geography?",
        "When is my Digital Design prototype due?",
        "Can you help me with my English essay?",
    ],
)
def test_new_subject_questions_are_not_off_topic(message):
    result = check_input(message)
    assert result.off_topic is False


def test_unrelated_message_is_off_topic():
    result = check_input("What's your favorite movie?")
    assert result.off_topic is True


def test_direct_answer_request_is_flagged():
    result = check_input("Just give me the answer to question 4")
    assert result.wants_direct_answer is True


def test_normal_concept_question_does_not_trigger_direct_answer_flag():
    result = check_input("Can you help me understand how to balance this equation?")
    assert result.wants_direct_answer is False
