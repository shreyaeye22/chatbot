"""Persistent, per-student memory: SQLite-backed, exposed to agents as a
retrieval tool rather than always injected into the prompt.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from difflib import SequenceMatcher

REPEAT_SIMILARITY_THRESHOLD = 0.8


def normalize_question(question: str) -> str:
    text = question.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def record_question(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    question: str,
    route: str,
    answered: bool = True,
    now: str | None = None,
) -> int:
    timestamp = now or datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO question_log (student_id, question, route, answered, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (student_id, question, route, int(answered), timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def get_recent_questions(
    conn: sqlite3.Connection, *, student_id: str, limit: int = 20
) -> list[dict]:
    rows = conn.execute(
        "SELECT id, question, route, answered, created_at FROM question_log "
        "WHERE student_id = ? ORDER BY id DESC LIMIT ?",
        (student_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def is_repeated_question(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    question: str,
    threshold: float = REPEAT_SIMILARITY_THRESHOLD,
    limit: int = 20,
) -> bool:
    """True if this student has asked a near-identical question before.

    Similarity is computed on normalized text (lowercased, punctuation
    stripped, whitespace collapsed) so wording noise like capitalization or
    a trailing question mark doesn't defeat the match.
    """
    normalized = normalize_question(question)
    for row in get_recent_questions(conn, student_id=student_id, limit=limit):
        past_normalized = normalize_question(row["question"])
        similarity = SequenceMatcher(None, normalized, past_normalized).ratio()
        if similarity >= threshold:
            return True
    return False
