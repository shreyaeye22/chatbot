"""Handles unmatched/low-confidence queries, and is the fallback route when
the orchestrator or a specialist agent fails outright (see agents/orchestrator.py)."""

from __future__ import annotations

from pydantic_ai import Agent

from agents.deps import AgentDeps
from toolsets import memory_tools

SYSTEM_PROMPT = """
You handle questions that couldn't be confidently answered as a logistics or concept question
for a Grade 9 MYP student.

Rules:
- Briefly and kindly tell the student their question has been noted for their teacher to follow
  up on.
- You may call check_if_repeated_question to mention if this looks like something they've asked
  before, which might mean the answer is already in their notes or a past class message.
- Do not attempt to answer subject content yourself, and do not guess at deadlines.
- Keep the response to 1-2 sentences.
"""

escalation_agent = Agent(
    model=None,
    deps_type=AgentDeps,
    output_type=str,
    system_prompt=SYSTEM_PROMPT,
    tools=[memory_tools.check_if_repeated_question],
)
