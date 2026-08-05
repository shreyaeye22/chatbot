"""Tools: search teacher-provided course notes/materials.

Ranking happens in skills.explain_concept (deterministic, testable);
this tool is just the SQLite lookup plus wiring the result through it.
"""

from __future__ import annotations

from pydantic_ai import RunContext

from agents.deps import AgentDeps
from data.db import get_connection
from skills.explain_concept import rank_content


def search_course_content(
    ctx: RunContext[AgentDeps], subject: str, topic_query: str
) -> list[dict]:
    """Search course notes for `subject` (one of the student's MYP4 subjects, e.g. math,
    biology, geography, digital design) for content relevant to `topic_query`. Returns the
    best-matching notes, best first.
    """
    conn = get_connection(ctx.deps.db_path)
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT subject, topic, content, source FROM course_content WHERE subject = ?",
                # Seed/stored subjects are lowercase; normalize so a differently-cased
                # subject from an LLM tool call (e.g. "Geography") still matches.
                (subject.strip().lower(),),
            ).fetchall()
        ]
    finally:
        conn.close()

    return rank_content(rows, topic_query, top_n=3)
