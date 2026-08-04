from __future__ import annotations

from capabilities.memory.student_memory import (
    get_recent_questions,
    is_repeated_question,
    record_question,
)


def test_is_repeated_question_detects_near_identical_wording(empty_conn):
    record_question(
        empty_conn, student_id="alice", question="When is my math homework due?", route="logistics"
    )

    assert is_repeated_question(
        empty_conn, student_id="alice", question="when is my math homework due"
    )


def test_is_repeated_question_false_for_a_genuinely_different_question(empty_conn):
    record_question(
        empty_conn, student_id="alice", question="When is my math homework due?", route="logistics"
    )

    assert not is_repeated_question(
        empty_conn, student_id="alice", question="Can you explain photosynthesis?"
    )


def test_is_repeated_question_only_matches_the_same_student(empty_conn):
    record_question(
        empty_conn, student_id="alice", question="When is my math homework due?", route="logistics"
    )

    assert not is_repeated_question(
        empty_conn, student_id="bob", question="When is my math homework due?"
    )


def test_record_question_is_retrievable_via_get_recent_questions(empty_conn):
    record_question(empty_conn, student_id="alice", question="q1", route="logistics")
    record_question(empty_conn, student_id="alice", question="q2", route="concept")

    recent = get_recent_questions(empty_conn, student_id="alice", limit=10)

    assert [row["question"] for row in recent] == ["q2", "q1"]  # most recent first
