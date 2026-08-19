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


@pytest.fixture
def vector_index_path(tmp_path: Path) -> str:
    """An empty, isolated Chroma index path - for tests that need AgentDeps to have
    *some* valid vector_index_path but don't exercise search_course_content.
    """
    return str(tmp_path / "vector_index")


@pytest.fixture
def seeded_index_path(seeded_db_path: str, tmp_path: Path) -> str:
    """A Chroma index pre-populated from the seeded course_content rows - for tests
    that actually call search_course_content and need real, findable notes.
    """
    from capabilities.retrieval import vector_store

    index_path = str(tmp_path / "seeded_vector_index")
    vector_store.ensure_index(index_path, seeded_db_path)
    return index_path
