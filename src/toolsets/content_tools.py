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
    """Search course notes for `subject` (math, physics, chemistry, or biology) for
    content relevant to `topic_query`. Returns the best-matching notes, best first.
    """
    conn = get_connection(ctx.deps.db_path)
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT subject, topic, content, source FROM course_content WHERE subject = ?",
                (subject,),
            ).fetchall()
        ]
    finally:
        conn.close()

    return rank_content(rows, topic_query, top_n=3)
