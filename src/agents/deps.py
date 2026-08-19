"""Shared dependency object passed into every agent run.

Kept minimal on purpose: tools open their own short-lived SQLite connection
from db_path rather than being handed a live connection, since Streamlit
reruns the script on every interaction.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentDeps:
    db_path: str
    student_id: str
    vector_index_path: str
