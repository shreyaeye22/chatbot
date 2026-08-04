from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from config.settings import SEED_DIR
from data.db import ensure_db, get_connection


@pytest.fixture
def seeded_db_path(tmp_path: Path) -> str:
    db_path = tmp_path / "test.db"
    ensure_db(db_path, SEED_DIR)
    return str(db_path)


@pytest.fixture
def seeded_conn(seeded_db_path: str) -> sqlite3.Connection:
    conn = get_connection(seeded_db_path)
    yield conn
    conn.close()


@pytest.fixture
def empty_conn(tmp_path: Path) -> sqlite3.Connection:
    from data.db import init_db

    db_path = tmp_path / "empty.db"
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()
