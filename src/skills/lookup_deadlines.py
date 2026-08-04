"""Task: find upcoming (or overdue-through-today) homework and assessment dates."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_upcoming(
    conn: sqlite3.Connection,
    *,
    subject: str | None = None,
    days_ahead: int = 14,
    today: date | None = None,
) -> list[dict]:
    """Homework + assessments due between today and today+days_ahead, soonest first."""
    today = today or date.today()
    horizon = today + timedelta(days=days_ahead)
    items: list[dict] = []

    hw_query = "SELECT subject, title, description, due_date FROM homework"
    hw_params: list[str] = []
    if subject:
        hw_query += " WHERE subject = ?"
        hw_params.append(subject)
    for row in conn.execute(hw_query, hw_params).fetchall():
        due = _parse_date(row["due_date"])
        if today <= due <= horizon:
            items.append(
                {
                    "subject": row["subject"],
                    "title": row["title"],
                    "description": row["description"],
                    "date": row["due_date"],
                    "type": "homework",
                }
            )

    as_query = "SELECT subject, title, description, assessment_date, assessment_type FROM assessments"
    as_params: list[str] = []
    if subject:
        as_query += " WHERE subject = ?"
        as_params.append(subject)
    for row in conn.execute(as_query, as_params).fetchall():
        due = _parse_date(row["assessment_date"])
        if today <= due <= horizon:
            items.append(
                {
                    "subject": row["subject"],
                    "title": row["title"],
                    "description": row["description"],
                    "date": row["assessment_date"],
                    "type": row["assessment_type"],
                }
            )

    items.sort(key=lambda item: item["date"])
    return items


def get_next(
    conn: sqlite3.Connection, *, subject: str | None = None, today: date | None = None
) -> dict | None:
    """The single soonest upcoming item, or None if nothing is scheduled."""
    upcoming = get_upcoming(conn, subject=subject, days_ahead=365, today=today)
    return upcoming[0] if upcoming else None
