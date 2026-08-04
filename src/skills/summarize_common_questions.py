"""Task: turn the logged questions into a teacher-facing digest of what's
being asked repeatedly, so class time spent re-explaining goes down."""

from __future__ import annotations

import sqlite3

from capabilities.memory.class_memory import get_common_questions


def build_teacher_digest(
    conn: sqlite3.Connection, *, limit: int = 5, min_count: int = 2
) -> list[dict]:
    """Common questions (asked min_count+ times), each with a ready-to-display summary line."""
    common = get_common_questions(conn, limit=limit, min_count=min_count)
    for item in common:
        item["summary"] = (
            f"Asked {item['count']}x by {item['student_count']} student(s) — {item['question']}"
        )
    return common
