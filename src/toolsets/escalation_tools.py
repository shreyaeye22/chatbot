"""Tools: write an unanswered/escalated question to the log for the teacher digest.

Called directly by the orchestrator once a turn is routed to escalation,
not exposed as an LLM tool, for the same reliability reason as
memory_tools' logging.
"""

from __future__ import annotations

import sqlite3

from capabilities.memory.student_memory import record_question


def log_unanswered_question(
    conn: sqlite3.Connection, *, student_id: str, question: str
) -> int:
    """Record a question the chatbot couldn't confidently answer, flagged for the teacher."""
    return record_question(
        conn, student_id=student_id, question=question, route="escalation", answered=False
    )
