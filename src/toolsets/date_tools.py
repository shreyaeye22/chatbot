"""Tools: get current date/week, so an agent can reason about "due soon"
without relying on the model's own (often wrong) sense of the current date.
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic_ai import RunContext

from agents.deps import AgentDeps


def get_today(ctx: RunContext[AgentDeps]) -> str:
    """Return today's date as an ISO string (YYYY-MM-DD)."""
    return date.today().isoformat()


def get_current_week_range(ctx: RunContext[AgentDeps]) -> dict:
    """Return the current Monday-to-Sunday week as {"start": ISO date, "end": ISO date}."""
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return {"start": start.isoformat(), "end": end.isoformat()}
