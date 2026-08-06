"""Teacher upload path: turn an uploaded worksheet/document into a course_content row.

Text-based formats (.docx, .pdf, .pptx, .txt, .md) are parsed deterministically here.
Images go through a separate LLM-based path (agents/vision_agent.py) since extracting
their content isn't a deterministic operation - see app.py's upload handler, which calls
`store_course_content` directly with the vision agent's transcription.

This is the "how does real ManageBac/Teams content get in" answer for a no-budget
course project: a teacher drops a file in via the Streamlit sidebar instead of a
live platform integration.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import BinaryIO

from docx import Document
from pptx import Presentation
from pypdf import PdfReader

SUPPORTED_DOCUMENT_EXTENSIONS = {".docx", ".pdf", ".pptx", ".txt", ".md"}


def extract_text_from_docx(file: BinaryIO | str) -> str:
    """Return the visible paragraph text of a .docx file, one paragraph per line."""
    document = Document(file)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_pdf(file: BinaryIO | str) -> str:
    """Return the extracted text of a .pdf file, one page per paragraph break."""
    reader = PdfReader(file)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(page.strip() for page in pages if page.strip())


def extract_text_from_pptx(file: BinaryIO | str) -> str:
    """Return the visible text of a .pptx file, one slide per paragraph break."""
    presentation = Presentation(file)
    slides_text = []
    for slide in presentation.slides:
        lines = [
            shape.text_frame.text.strip()
            for shape in slide.shapes
            if shape.has_text_frame and shape.text_frame.text.strip()
        ]
        if lines:
            slides_text.append("\n".join(lines))
    return "\n\n".join(slides_text)


def extract_text_from_plain_text(file: BinaryIO | str) -> str:
    """Return the content of a .txt/.md file as-is."""
    if isinstance(file, (str, Path)):
        return Path(file).read_text(encoding="utf-8").strip()
    raw = file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return raw.strip()


_EXTRACTORS = {
    ".docx": extract_text_from_docx,
    ".pdf": extract_text_from_pdf,
    ".pptx": extract_text_from_pptx,
    ".txt": extract_text_from_plain_text,
    ".md": extract_text_from_plain_text,
}


def extract_text(file: BinaryIO | str, filename: str) -> str:
    """Dispatch to the right extractor for `filename`'s extension."""
    suffix = Path(filename).suffix.lower()
    extractor = _EXTRACTORS.get(suffix)
    if extractor is None:
        raise ValueError(
            f"Unsupported file type {suffix!r} for {filename!r}; "
            f"expected one of {sorted(SUPPORTED_DOCUMENT_EXTENSIONS)}"
        )
    return extractor(file)


def store_course_content(
    conn: sqlite3.Connection, *, subject: str, topic: str, content: str, source_name: str
) -> int:
    """Insert already-extracted text as a course_content row. Returns the new row's id."""
    if not content:
        raise ValueError(f"No content to store for {source_name!r}")

    cursor = conn.execute(
        "INSERT INTO course_content (subject, topic, content, source) VALUES (?, ?, ?, ?)",
        (subject, topic, content, source_name),
    )
    conn.commit()
    return cursor.lastrowid


def ingest_document(
    conn: sqlite3.Connection,
    *,
    file: BinaryIO | str,
    subject: str,
    topic: str,
    source_name: str,
) -> int:
    """Parse an uploaded document (.docx/.pdf/.pptx/.txt/.md) and store it as a
    course_content row. Returns the new row's id.
    """
    text = extract_text(file, source_name)
    return store_course_content(
        conn, subject=subject, topic=topic, content=text, source_name=source_name
    )
