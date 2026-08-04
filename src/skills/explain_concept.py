"""Task: pick the course_content row that best matches a student's concept question.

Deterministic keyword-overlap ranking, kept separate from the LLM call so
"does this question surface the right notes" is unit-testable without an
agent or model in the loop.
"""

from __future__ import annotations

import re


def _keywords(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9']+", text.lower()) if len(word) > 2}


def _score(row: dict, query_words: set[str]) -> int:
    row_words = _keywords(f"{row['topic']} {row['content']}")
    return len(query_words & row_words)


def select_best_content(rows: list[dict], query: str) -> dict | None:
    """Best-matching row for `query`, or None if nothing shares a keyword with it."""
    ranked = rank_content(rows, query, top_n=1)
    return ranked[0] if ranked else None


def rank_content(rows: list[dict], query: str, top_n: int = 3) -> list[dict]:
    """Rows ranked by keyword overlap with `query`, best first, dropping zero-overlap rows.

    Returning a short, pre-ranked list (rather than every row for the
    subject) keeps the agent's context small and avoids relying on a
    (possibly small) model to do its own relevance judgement.
    """
    if not rows:
        return []

    query_words = _keywords(query)
    scored = [(row, _score(row, query_words)) for row in rows]
    scored = [(row, score) for row, score in scored if score > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [row for row, _score_value in scored[:top_n]]
