"""Tools: thin wrappers exposing student memory to agents.

Question *logging* is done deterministically by the orchestrator after
routing (see agents/orchestrator.py), not via an agent-invoked tool — that
way every question gets logged even if a small model forgets to call a
"log this" tool. This module only exposes read access.
"""

from __future__ import annotations

from pydantic_ai import RunContext

from agents.deps import AgentDeps
from capabilities.memory.student_memory import is_repeated_question
from data.db import get_connection


def check_if_repeated_question(ctx: RunContext[AgentDeps], question: str) -> bool:
    """Check whether this student has already asked a near-identical question recently."""
    conn = get_connection(ctx.deps.db_path)
    try:
        return is_repeated_question(conn, student_id=ctx.deps.student_id, question=question)
    finally:
        conn.close()
