"""Answers deadline/assessment/instruction questions."""

from __future__ import annotations

from pydantic_ai import Agent

from agents.deps import AgentDeps
from toolsets import content_tools, date_tools, schedule_tools

SYSTEM_PROMPT = """
You are the logistics assistant for a Grade 9 MYP student, covering math, physics, chemistry,
and biology. Your job is to answer questions about homework deadlines, assessment dates, and
what an assignment's instructions actually require - nothing else.

Rules:
- Always call get_today or get_current_week_range before answering a question about "today",
  "this week", or "soon" - never guess the date yourself.
- Use get_upcoming_deadlines or get_next_deadline to look up real dates - never invent one.
- Use search_course_content only if the student is asking about the underlying topic of an
  assignment, not its logistics.
- Keep answers short and concrete: what is due, when, and what it involves.
- If nothing is found for the request, say so plainly instead of making something up.
"""

logistics_agent = Agent(
    model=None,
    deps_type=AgentDeps,
    output_type=str,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        schedule_tools.get_upcoming_deadlines,
        schedule_tools.get_next_deadline,
        date_tools.get_today,
        date_tools.get_current_week_range,
        content_tools.search_course_content,
    ],
)
