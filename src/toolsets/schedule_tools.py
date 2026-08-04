"""Tools: query SQLite for homework/assessment dates.

Thin wrappers over skills.lookup_deadlines — the actual date-range/merge
logic lives there so it can be unit tested without an agent or LLM call.
"""

from __future__ import annotations

from pydantic_ai import RunContext

from agents.deps import AgentDeps
from data.db import get_connection
from skills.lookup_deadlines import get_next, get_upcoming


def get_upcoming_deadlines(
    ctx: RunContext[AgentDeps], subject: str | None = None, days_ahead: int = 14
) -> list[dict]:
    """List homework and assessments due in the next `days_ahead` days.

    `subject` optionally filters to one of: math, physics, chemistry, biology.
    """
    conn = get_connection(ctx.deps.db_path)
    try:
        return get_upcoming(conn, subject=subject, days_ahead=days_ahead)
    finally:
        conn.close()


def get_next_deadline(ctx: RunContext[AgentDeps], subject: str | None = None) -> dict | None:
    """The single soonest upcoming homework or assessment item, or null if none is scheduled.

    `subject` optionally filters to one of: math, physics, chemistry, biology.
    """
    conn = get_connection(ctx.deps.db_path)
    try:
        return get_next(conn, subject=subject)
    finally:
        conn.close()
