from __future__ import annotations

from capabilities.memory.student_memory import record_question
from skills.summarize_common_questions import build_teacher_digest


def test_digest_ranks_the_most_asked_question_first(empty_conn):
    record_question(
        empty_conn, student_id="alice", question="When is the math test?", route="logistics"
    )
    record_question(
        empty_conn, student_id="bob", question="when is the math test", route="logistics"
    )
    record_question(
        empty_conn, student_id="carol", question="when is the math test?!", route="logistics"
    )
    record_question(
        empty_conn, student_id="alice", question="What is photosynthesis?", route="concept"
    )

    digest = build_teacher_digest(empty_conn, limit=5, min_count=1)

    assert digest[0]["question"] == "When is the math test?"
    assert digest[0]["count"] == 3
    assert digest[0]["student_count"] == 3
    assert "Asked 3x" in digest[0]["summary"]


def test_digest_respects_min_count_threshold(empty_conn):
    record_question(empty_conn, student_id="alice", question="unique question", route="concept")

    digest = build_teacher_digest(empty_conn, min_count=2)

    assert digest == []
