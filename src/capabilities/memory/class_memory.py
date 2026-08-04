"""Class-level (aggregate) memory: rolls up repeated questions across all
students to power the teacher-facing "most common questions" digest.
"""

from __future__ import annotations

import sqlite3

from capabilities.memory.student_memory import normalize_question


def get_common_questions(
    conn: sqlite3.Connection, *, limit: int = 5, min_count: int = 1
) -> list[dict]:
    """Cluster logged questions by normalized text and rank by frequency.

    Returns a list of {question, count, route, student_count} ordered most
    asked first. `question` is the earliest-seen original phrasing for that
    cluster, kept for readability in the teacher digest.
    """
    rows = conn.execute(
        "SELECT question, route, student_id FROM question_log ORDER BY id ASC"
    ).fetchall()

    clusters: dict[str, dict] = {}
    for row in rows:
        key = normalize_question(row["question"])
        if key not in clusters:
            clusters[key] = {
                "question": row["question"],
                "route": row["route"],
                "count": 0,
                "students": set(),
            }
        clusters[key]["count"] += 1
        clusters[key]["students"].add(row["student_id"])

    digest = [
        {
            "question": c["question"],
            "route": c["route"],
            "count": c["count"],
            "student_count": len(c["students"]),
        }
        for c in clusters.values()
        if c["count"] >= min_count
    ]
    digest.sort(key=lambda c: c["count"], reverse=True)
    return digest[:limit]
