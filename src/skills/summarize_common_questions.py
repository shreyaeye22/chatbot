"""Task: turn the logged questions into ready-to-send prompt suggestions for
students, surfacing what's already being asked repeatedly."""

from __future__ import annotations

import sqlite3

from capabilities.memory.class_memory import get_common_questions


def build_faq_prompts(conn: sqlite3.Connection, *, limit: int = 5) -> list[str]:
    """Top asked questions, phrased ready to show as one-click prompt suggestions for students."""
    common = get_common_questions(conn, limit=limit, min_count=1)
    return [item["question"] for item in common]
