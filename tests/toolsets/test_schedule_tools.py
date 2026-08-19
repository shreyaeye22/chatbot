from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from agents.deps import AgentDeps
from data.db import get_connection, init_db
from toolsets.schedule_tools import get_next_deadline, get_upcoming_deadlines


def _fake_ctx(db_path: str):
    return SimpleNamespace(
        deps=AgentDeps(db_path=db_path, student_id="demo_student", vector_index_path="unused")
    )


def _empty_db_path(tmp_path) -> str:
    db_path = str(tmp_path / "app.db")
    init_db(db_path)
    return db_path


def _insert_homework_due_in(db_path: str, subject: str, title: str, days_from_now: int) -> None:
    conn = get_connection(db_path)
    due_date = (date.today() + timedelta(days=days_from_now)).isoformat()
    conn.execute(
        "INSERT INTO homework (subject, title, description, assigned_date, due_date) "
        "VALUES (?, ?, 'desc', ?, ?)",
        (subject, title, date.today().isoformat(), due_date),
    )
    conn.commit()
    conn.close()


def test_get_upcoming_deadlines_reads_from_the_db_and_filters_by_subject(tmp_path):
    db_path = _empty_db_path(tmp_path)
    _insert_homework_due_in(db_path, "math", "fresh math homework", days_from_now=2)
    _insert_homework_due_in(db_path, "physics", "fresh physics homework", days_from_now=2)
    ctx = _fake_ctx(db_path)

    upcoming = get_upcoming_deadlines(ctx, subject="math", days_ahead=14)

    assert [item["title"] for item in upcoming] == ["fresh math homework"]


def test_get_next_deadline_returns_the_soonest_item(tmp_path):
    db_path = _empty_db_path(tmp_path)
    _insert_homework_due_in(db_path, "biology", "later item", days_from_now=10)
    _insert_homework_due_in(db_path, "biology", "soonest item", days_from_now=1)
    ctx = _fake_ctx(db_path)

    next_item = get_next_deadline(ctx, subject="biology")

    assert next_item["title"] == "soonest item"
