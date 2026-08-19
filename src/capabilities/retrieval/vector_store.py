"""Vector-embedding search over course_content, via a local ChromaDB index.

SQLite's `course_content` table stays the source of truth; this Chroma index is a
disposable projection of it, kept in sync by `index_row()` on every write and
self-healed by `ensure_index()` at boot - its own prior contents are never trusted,
only ever compared against `course_content`'s row count and rebuilt on mismatch.
Embedding runs locally via Chroma's bundled ONNX model (no LLM call, no external
API), which is what keeps this free and safe on a machine with no persistent disk.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings

COLLECTION_NAME = "course_content"


@lru_cache(maxsize=1)
def _embedding_function():
    """The ONNX MiniLM embedding model, loaded once per process regardless of
    how many index paths/collections use it (expensive to construct, cheap to reuse).
    """
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    return DefaultEmbeddingFunction()


@lru_cache(maxsize=None)
def get_client(persist_path: str) -> chromadb.ClientAPI:
    """One Chroma client per persist path, memoized - Chroma's own guidance is
    against multiple client instances on the same path in one process.
    """
    return chromadb.PersistentClient(
        path=persist_path, settings=Settings(anonymized_telemetry=False)
    )


@lru_cache(maxsize=None)
def get_collection(persist_path: str) -> Collection:
    client = get_client(persist_path)
    return client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=_embedding_function()
    )


def _document_text(row: dict) -> str:
    """Text actually embedded for a row - topic first since it often echoes the
    keywords a short student question would use.
    """
    return f"{row['topic']}\n\n{row['content']}"


def _metadata(row: dict) -> dict:
    return {
        "subject": row["subject"],
        "topic": row["topic"],
        "content": row["content"],
        "source": row["source"],
    }


def index_row(collection: Collection, row: dict) -> None:
    """Embed and upsert one course_content row (`row` has id/subject/topic/content/source).

    Upsert, not add, so re-indexing an existing id (e.g. on `reindex_all`) never
    creates a duplicate.
    """
    collection.upsert(
        ids=[str(row["id"])],
        documents=[_document_text(row)],
        metadatas=[_metadata(row)],
    )


def reindex_all(collection: Collection, conn: sqlite3.Connection) -> int:
    """Wipe and rebuild the collection from every course_content row.

    Full rebuild rather than an incremental diff - simpler to reason about ("Chroma
    is fully derived, never trust its prior contents") and cheap at this scale.
    Returns the number of rows indexed.
    """
    existing_ids = collection.get(include=[])["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)

    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT id, subject, topic, content, source FROM course_content"
        ).fetchall()
    ]
    if not rows:
        return 0

    collection.upsert(
        ids=[str(row["id"]) for row in rows],
        documents=[_document_text(row) for row in rows],
        metadatas=[_metadata(row) for row in rows],
    )
    return len(rows)


def ensure_index(vector_path: str | Path, db_path: str | Path) -> None:
    """Rebuild the index from SQLite if it's empty or out of sync. Safe to call every boot.

    This is what makes the index safe against a wiped/ephemeral filesystem (e.g. a
    Streamlit Community Cloud redeploy): the collection's row count is compared
    against `course_content`'s, and rebuilt from SQLite on any mismatch.
    """
    from data.db import get_connection

    collection = get_collection(str(vector_path))
    conn = get_connection(db_path)
    try:
        row_count = conn.execute("SELECT COUNT(*) AS n FROM course_content").fetchone()["n"]
        if collection.count() != row_count:
            reindex_all(collection, conn)
    finally:
        conn.close()


def search(collection: Collection, *, subject: str, query: str, top_k: int = 3) -> list[dict]:
    """Semantic top-k search over `subject`'s notes for `query`, best first.

    Returns `{subject, topic, content, source}` dicts read straight from Chroma's
    metadata - no SQLite round-trip needed at query time.
    """
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        # Seed/stored subjects are lowercase; normalize so a differently-cased
        # subject from an LLM tool call (e.g. "Geography") still matches.
        where={"subject": subject.strip().lower()},
    )
    return list(results["metadatas"][0])
