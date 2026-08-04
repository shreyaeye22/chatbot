from __future__ import annotations

from capabilities.memory.class_memory import get_common_questions
from capabilities.memory.student_memory import record_question


def test_get_common_questions_ranks_by_frequency_across_students(empty_conn):
    record_question(empty_conn, student_id="alice", question="When is the quiz?", route="logistics")
    record_question(empty_conn, student_id="bob", question="when is the quiz?", route="logistics")
    record_question(
        empty_conn, student_id="carol", question="Explain photosynthesis", route="concept"
    )

    common = get_common_questions(empty_conn, limit=5, min_count=1)

    assert common[0]["question"] == "When is the quiz?"
    assert common[0]["count"] == 2
    assert common[0]["student_count"] == 2
    assert common[1]["count"] == 1


def test_get_common_questions_respects_limit(empty_conn):
    for i in range(5):
        record_question(empty_conn, student_id=f"student{i}", question=f"q{i}", route="concept")

    common = get_common_questions(empty_conn, limit=2, min_count=1)

    assert len(common) == 2
