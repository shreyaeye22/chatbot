from __future__ import annotations

from toolsets.escalation_tools import log_unanswered_question


def test_log_unanswered_question_marks_route_and_unanswered(empty_conn):
    log_unanswered_question(empty_conn, student_id="alice", question="Why is the sky blue?")

    row = empty_conn.execute(
        "SELECT student_id, question, route, answered FROM question_log"
    ).fetchone()

    assert row["student_id"] == "alice"
    assert row["question"] == "Why is the sky blue?"
    assert row["route"] == "escalation"
    assert row["answered"] == 0
