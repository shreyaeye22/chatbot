from __future__ import annotations

from capabilities.memory.student_memory import record_question
from skills.summarize_common_questions import build_faq_prompts


def test_faq_prompts_ranks_most_asked_first(empty_conn):
    record_question(
        empty_conn, student_id="alice", question="When is the math test?", route="logistics"
    )
    record_question(
        empty_conn, student_id="bob", question="when is the math test", route="logistics"
    )
    record_question(
        empty_conn, student_id="carol", question="What is photosynthesis?", route="concept"
    )

    prompts = build_faq_prompts(empty_conn, limit=5)

    assert prompts[0] == "When is the math test?"
    assert "What is photosynthesis?" in prompts


def test_faq_prompts_includes_questions_asked_only_once(empty_conn):
    record_question(empty_conn, student_id="alice", question="unique question", route="concept")

    prompts = build_faq_prompts(empty_conn)

    assert prompts == ["unique question"]


def test_faq_prompts_respects_limit(empty_conn):
    for i in range(7):
        record_question(empty_conn, student_id=f"student{i}", question=f"q{i}", route="concept")

    prompts = build_faq_prompts(empty_conn, limit=5)

    assert len(prompts) == 5
