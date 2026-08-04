"""Teacher upload path: turn an uploaded .docx worksheet into course_content rows.

This is the "how does real ManageBac/Teams content get in" answer for a
no-budget course project: a teacher drops a Word doc in via the Streamlit
sidebar instead of a live platform integration.
"""

from __future__ import annotations

import sqlite3
from typing import BinaryIO

from docx import Document


def extract_text_from_docx(file: BinaryIO | str) -> str:
    """Return the visible paragraph text of a .docx file, one paragraph per line."""
    document = Document(file)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def ingest_docx(
    conn: sqlite3.Connection,
    *,
    file: BinaryIO | str,
    subject: str,
    topic: str,
    source_name: str,
) -> int:
    """Parse an uploaded worksheet and store it as a course_content row.

    Returns the new row's id.
    """
    text = extract_text_from_docx(file)
    if not text:
        raise ValueError(f"No readable text found in {source_name!r}")

    cursor = conn.execute(
        "INSERT INTO course_content (subject, topic, content, source) VALUES (?, ?, ?, ?)",
        (subject, topic, text, source_name),
    )
    conn.commit()
    return cursor.lastrowid
