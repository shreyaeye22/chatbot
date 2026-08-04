from __future__ import annotations

from skills.clarify_instructions import extract_key_instruction_points


def test_extracts_only_sentences_with_action_verbs():
    raw = (
        "This assignment covers linear equations. "
        "Submit your worksheet by Friday. "
        "It was assigned in class on Monday. "
        "Bring a calculator to the quiz."
    )

    points = extract_key_instruction_points(raw)

    assert points == [
        "Submit your worksheet by Friday.",
        "Bring a calculator to the quiz.",
    ]


def test_falls_back_to_all_sentences_when_no_action_verb_found():
    raw = "This is background context. It has no instructions in it."

    points = extract_key_instruction_points(raw)

    assert points == ["This is background context.", "It has no instructions in it."]


def test_handles_empty_input():
    assert extract_key_instruction_points("") == []
