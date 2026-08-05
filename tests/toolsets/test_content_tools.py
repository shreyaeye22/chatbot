from __future__ import annotations

from types import SimpleNamespace

from agents.deps import AgentDeps
from toolsets.content_tools import search_course_content


def _fake_ctx(db_path: str):
    return SimpleNamespace(deps=AgentDeps(db_path=db_path, student_id="demo_student"))


def test_search_course_content_finds_the_seeded_newtons_laws_note(seeded_db_path):
    ctx = _fake_ctx(seeded_db_path)

    results = search_course_content(ctx, subject="physics", topic_query="newton's second law force")

    assert results
    assert results[0]["topic"] == "newton's laws"


def test_search_course_content_only_searches_the_given_subject(seeded_db_path):
    ctx = _fake_ctx(seeded_db_path)

    results = search_course_content(ctx, subject="biology", topic_query="force acceleration")

    assert all(row["subject"] == "biology" for row in results)


def test_search_course_content_subject_match_is_case_insensitive(seeded_db_path):
    ctx = _fake_ctx(seeded_db_path)

    results = search_course_content(
        ctx, subject="Geography", topic_query="population pyramid age structure"
    )

    assert results
    assert results[0]["topic"] == "population pyramids"
