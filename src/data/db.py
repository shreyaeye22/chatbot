"""SQLite schema and connection helper.

Streamlit reruns the whole script on every interaction, so connections are
short-lived (opened, used, closed) rather than held as global/session state.
SQLite handles that access pattern fine at this scale.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS homework (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    assigned_date TEXT NOT NULL,
    due_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    assessment_date TEXT NOT NULL,
    assessment_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS course_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'seed',
    owner TEXT NOT NULL DEFAULT 'Teacher',
    uploaded_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS question_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    question TEXT NOT NULL,
    route TEXT NOT NULL,
    answered INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""

# Sentinel course_content.created_at for rows that predate upload-timestamp tracking
# (seed data, and pre-existing rows backfilled by _ensure_upload_metadata_columns) - old
# enough that real uploads always sort ahead of it under "newest first" ordering.
SEED_UPLOAD_TIMESTAMP = "1970-01-01T00:00:00Z"


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_owner_column(conn: sqlite3.Connection) -> None:
    """Backfill course_content.owner for DBs created before this column existed.

    No-ops if already present (fresh DBs get it straight from SCHEMA_SQL).
    SQLite's ADD COLUMN ... DEFAULT backfills existing rows automatically, so
    no per-row UPDATE is needed.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(course_content)")}
    if "owner" not in columns:
        conn.execute("ALTER TABLE course_content ADD COLUMN owner TEXT NOT NULL DEFAULT 'Teacher'")


def _ensure_upload_metadata_columns(conn: sqlite3.Connection) -> None:
    """Backfill course_content.uploaded_by/created_at for DBs created before these
    columns existed. Rows with no recorded created_at (freshly added column, or an
    empty value some other way) predate upload tracking, so they're backfilled to
    SEED_UPLOAD_TIMESTAMP rather than left unsortable. No-ops (past the ALTERs) once
    already backfilled, so it's safe to call on every init_db.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(course_content)")}
    if "uploaded_by" not in columns:
        conn.execute("ALTER TABLE course_content ADD COLUMN uploaded_by TEXT NOT NULL DEFAULT ''")
    if "created_at" not in columns:
        conn.execute("ALTER TABLE course_content ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "UPDATE course_content SET created_at = ? WHERE created_at = ''", (SEED_UPLOAD_TIMESTAMP,)
    )


def init_db(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _ensure_owner_column(conn)
        _ensure_upload_metadata_columns(conn)
        conn.commit()
    finally:
        conn.close()


def _table_is_empty(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return row["n"] == 0


def seed_db(db_path: str | Path, seed_dir: str | Path) -> None:
    """Load placeholder homework/assessment/content JSON into an empty DB.

    No-ops per-table if that table already has rows, so re-running on an
    already-seeded (or teacher-uploaded) DB is safe.
    """
    seed_dir = Path(seed_dir)
    conn = get_connection(db_path)
    try:
        if _table_is_empty(conn, "homework"):
            rows = json.loads((seed_dir / "homework.json").read_text(encoding="utf-8"))
            conn.executemany(
                "INSERT INTO homework (subject, title, description, assigned_date, due_date) "
                "VALUES (:subject, :title, :description, :assigned_date, :due_date)",
                rows,
            )
        if _table_is_empty(conn, "assessments"):
            rows = json.loads((seed_dir / "assessments.json").read_text(encoding="utf-8"))
            conn.executemany(
                "INSERT INTO assessments (subject, title, description, assessment_date, assessment_type) "
                "VALUES (:subject, :title, :description, :assessment_date, :assessment_type)",
                rows,
            )
        if _table_is_empty(conn, "course_content"):
            rows = json.loads((seed_dir / "course_content.json").read_text(encoding="utf-8"))
            conn.executemany(
                "INSERT INTO course_content (subject, topic, content, source, created_at) "
                "VALUES (:subject, :topic, :content, :source, :created_at)",
                [{**row, "created_at": SEED_UPLOAD_TIMESTAMP} for row in rows],
            )
        conn.commit()
    finally:
        conn.close()


def ensure_db(db_path: str | Path, seed_dir: str | Path) -> None:
    """Create the DB (if missing) and seed it (if empty). Safe to call every app run."""
    init_db(db_path)
    seed_db(db_path, seed_dir)
