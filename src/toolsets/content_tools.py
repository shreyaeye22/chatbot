"""Tools: search teacher-provided course notes/materials.

Semantic ranking happens in capabilities.retrieval.vector_store (a local ChromaDB
index, deterministic given the embedding model, no LLM call); this tool just wires
the result through it. No SQLite lookup here - the vector index's metadata already
carries the full row, so a search never needs to touch course_content directly
(SQLite stays the source of truth for what the index gets rebuilt from, not for
answering a single query).
"""

from __future__ import annotations

from pydantic_ai import RunContext

from agents.deps import AgentDeps
from capabilities.retrieval import vector_store


def search_course_content(
    ctx: RunContext[AgentDeps], subject: str, topic_query: str
) -> list[dict]:
    """Search course notes for `subject` (one of the student's MYP4 subjects, e.g. math,
    biology, geography, digital design) for content relevant to `topic_query`. Returns the
    best-matching notes, best first.
    """
    collection = vector_store.get_collection(ctx.deps.vector_index_path)
    return vector_store.search(collection, subject=subject, query=topic_query, top_k=3)
