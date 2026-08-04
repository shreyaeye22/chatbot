from __future__ import annotations

from types import SimpleNamespace

from agents.deps import AgentDeps
from capabilities.memory.student_memory import record_question
from data.db import get_connection, init_db
from toolsets.memory_tools import check_if_repeated_question


def _fake_ctx(db_path: str, student_id: str = "demo_student"):
    return SimpleNamespace(deps=AgentDeps(db_path=db_path, student_id=student_id))


def test_check_if_repeated_question(tmp_path):
    db_path = str(tmp_path / "app.db")
    init_db(db_path)
    conn = get_connection(db_path)
    record_question(
        conn, student_id="demo_student", question="When is the quiz?", route="logistics"
    )
    conn.close()

    ctx = _fake_ctx(db_path)
    assert check_if_repeated_question(ctx, "when is the quiz") is True
    assert check_if_repeated_question(ctx, "what is photosynthesis") is False
