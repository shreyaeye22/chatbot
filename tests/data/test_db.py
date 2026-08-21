from __future__ import annotations

import sqlite3

from config.settings import SUPPORTED_SUBJECTS
from data.db import SEED_UPLOAD_TIMESTAMP, ensure_db, get_connection, init_db


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


def test_seeded_course_content_rows_default_to_teacher_owner(seeded_conn: sqlite3.Connection):
    owners = {row["owner"] for row in seeded_conn.execute("SELECT DISTINCT owner FROM course_content")}

    assert owners == {"Teacher"}


def test_seeded_course_content_rows_have_the_seed_upload_timestamp(seeded_conn: sqlite3.Connection):
    timestamps = {
        row["created_at"] for row in seeded_conn.execute("SELECT DISTINCT created_at FROM course_content")
    }

    assert timestamps == {SEED_UPLOAD_TIMESTAMP}


def test_seeded_course_content_rows_have_no_uploaded_by(seeded_conn: sqlite3.Connection):
    uploaded_by = {
        row["uploaded_by"] for row in seeded_conn.execute("SELECT DISTINCT uploaded_by FROM course_content")
    }

    assert uploaded_by == {""}


def test_init_db_migrates_existing_course_content_table_to_add_owner_column(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = get_connection(db_path)
    try:
        conn.execute(
            "CREATE TABLE course_content ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, topic TEXT NOT NULL, "
            "content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'seed')"
        )
        conn.execute(
            "INSERT INTO course_content (subject, topic, content, source) VALUES (?, ?, ?, ?)",
            ("math", "algebra", "notes", "legacy.txt"),
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db_path)  # should not raise, and should backfill the new column

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT owner FROM course_content WHERE source = 'legacy.txt'").fetchone()
    finally:
        conn.close()
    assert row["owner"] == "Teacher"


def test_init_db_owner_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "app.db"

    init_db(db_path)
    init_db(db_path)  # second call must not raise (e.g. duplicate ALTER TABLE)

    conn = get_connection(db_path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(course_content)")}
    finally:
        conn.close()
    assert "owner" in columns


def test_init_db_migrates_existing_table_to_add_upload_metadata_columns(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = get_connection(db_path)
    try:
        conn.execute(
            "CREATE TABLE course_content ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, topic TEXT NOT NULL, "
            "content TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'seed', "
            "owner TEXT NOT NULL DEFAULT 'Teacher')"
        )
        conn.execute(
            "INSERT INTO course_content (subject, topic, content, source) VALUES (?, ?, ?, ?)",
            ("math", "algebra", "notes", "legacy.txt"),
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db_path)  # should not raise, and should backfill both new columns

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT uploaded_by, created_at FROM course_content WHERE source = 'legacy.txt'"
        ).fetchone()
    finally:
        conn.close()
    assert row["uploaded_by"] == ""
    assert row["created_at"] == SEED_UPLOAD_TIMESTAMP


def test_init_db_upload_metadata_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "app.db"

    init_db(db_path)
    init_db(db_path)  # second call must not raise (e.g. duplicate ALTER TABLE)

    conn = get_connection(db_path)
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(course_content)")}
    finally:
        conn.close()
    assert {"uploaded_by", "created_at"} <= columns
