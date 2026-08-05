from __future__ import annotations

import sqlite3

from config.settings import SUPPORTED_SUBJECTS
from data.db import ensure_db, get_connection, init_db


def test_init_db_creates_expected_tables(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)

    conn = get_connection(db_path)
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert {"homework", "assessments", "course_content", "question_log"} <= tables


def test_ensure_db_loads_seed_data_once(tmp_path, seeded_conn: sqlite3.Connection):
    homework_count = seeded_conn.execute("SELECT COUNT(*) AS n FROM homework").fetchone()["n"]
    assessment_count = seeded_conn.execute(
        "SELECT COUNT(*) AS n FROM assessments"
    ).fetchone()["n"]
    content_count = seeded_conn.execute(
        "SELECT COUNT(*) AS n FROM course_content"
    ).fetchone()["n"]

    assert homework_count > 0
    assert assessment_count > 0
    assert content_count > 0


def test_ensure_db_does_not_duplicate_seed_rows_on_second_call(seeded_db_path):
    from config.settings import SEED_DIR

    ensure_db(seeded_db_path, SEED_DIR)  # second call, DB already seeded

    conn = get_connection(seeded_db_path)
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM homework").fetchone()["n"]
    finally:
        conn.close()

    # Same count as a single seed pass, not doubled.
    import json
    from pathlib import Path

    expected = len(json.loads((Path(SEED_DIR) / "homework.json").read_text(encoding="utf-8")))
    assert count == expected


def test_every_supported_subject_has_seed_course_content(seeded_conn: sqlite3.Connection):
    seeded_subjects = {
        row["subject"] for row in seeded_conn.execute("SELECT DISTINCT subject FROM course_content")
    }

    assert set(SUPPORTED_SUBJECTS) <= seeded_subjects
