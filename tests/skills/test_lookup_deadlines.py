from __future__ import annotations

from datetime import date

from skills.lookup_deadlines import get_next, get_upcoming


def _insert_homework(conn, subject, title, due_date):
    conn.execute(
        "INSERT INTO homework (subject, title, description, assigned_date, due_date) "
        "VALUES (?, ?, 'desc', '2026-08-01', ?)",
        (subject, title, due_date),
    )


def _insert_assessment(conn, subject, title, assessment_date, assessment_type="test"):
    conn.execute(
        "INSERT INTO assessments (subject, title, description, assessment_date, assessment_type) "
        "VALUES (?, ?, 'desc', ?, ?)",
        (subject, title, assessment_date, assessment_type),
    )


def test_get_upcoming_excludes_items_outside_the_date_window(empty_conn):
    today = date(2026, 8, 4)
    _insert_homework(empty_conn, "math", "past due", "2026-08-01")  # before today
    _insert_homework(empty_conn, "math", "in window", "2026-08-06")  # within 14 days
    _insert_homework(empty_conn, "math", "too far", "2026-09-01")  # outside 14 days
    empty_conn.commit()

    upcoming = get_upcoming(empty_conn, days_ahead=14, today=today)

    titles = {item["title"] for item in upcoming}
    assert titles == {"in window"}


def test_get_upcoming_filters_by_subject(empty_conn):
    today = date(2026, 8, 4)
    _insert_homework(empty_conn, "math", "math hw", "2026-08-06")
    _insert_homework(empty_conn, "physics", "physics hw", "2026-08-06")
    empty_conn.commit()

    upcoming = get_upcoming(empty_conn, subject="math", days_ahead=14, today=today)

    assert [item["title"] for item in upcoming] == ["math hw"]


def test_get_upcoming_merges_homework_and_assessments_sorted_by_date(empty_conn):
    today = date(2026, 8, 4)
    _insert_homework(empty_conn, "math", "hw due later", "2026-08-10")
    _insert_assessment(empty_conn, "math", "quiz due sooner", "2026-08-05")
    empty_conn.commit()

    upcoming = get_upcoming(empty_conn, days_ahead=14, today=today)

    assert [item["title"] for item in upcoming] == ["quiz due sooner", "hw due later"]
    assert upcoming[1]["type"] == "homework"
    assert upcoming[0]["type"] == "test"


def test_get_next_returns_the_single_soonest_item(empty_conn):
    today = date(2026, 8, 4)
    _insert_homework(empty_conn, "biology", "later", "2026-08-20")
    _insert_homework(empty_conn, "biology", "soonest", "2026-08-05")
    empty_conn.commit()

    next_item = get_next(empty_conn, today=today)

    assert next_item["title"] == "soonest"


def test_get_next_returns_none_when_nothing_scheduled(empty_conn):
    assert get_next(empty_conn, today=date(2026, 8, 4)) is None


def test_get_upcoming_subject_filter_is_case_insensitive(empty_conn):
    today = date(2026, 8, 4)
    _insert_homework(empty_conn, "geography", "geo hw", "2026-08-06")
    empty_conn.commit()

    upcoming = get_upcoming(empty_conn, subject="Geography", days_ahead=14, today=today)

    assert [item["title"] for item in upcoming] == ["geo hw"]
