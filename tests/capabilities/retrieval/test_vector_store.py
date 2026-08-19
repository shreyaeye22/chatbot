from __future__ import annotations

from capabilities.retrieval import vector_store


def _row(row_id, *, subject, topic, content, source="seed"):
    return {"id": row_id, "subject": subject, "topic": topic, "content": content, "source": source}


def _insert_row(conn, *, subject, topic, content, source="seed"):
    cursor = conn.execute(
        "INSERT INTO course_content (subject, topic, content, source) VALUES (?, ?, ?, ?)",
        (subject, topic, content, source),
    )
    conn.commit()
    return cursor.lastrowid


def test_index_row_makes_it_findable_by_search(tmp_path):
    collection = vector_store.get_collection(str(tmp_path / "vector_index"))
    vector_store.index_row(
        collection,
        _row(1, subject="physics", topic="newton's laws", content="F = m * a, force equals mass times acceleration."),
    )

    results = vector_store.search(collection, subject="physics", query="what is the force equation")

    assert results
    assert results[0]["topic"] == "newton's laws"


def test_search_only_returns_rows_for_the_requested_subject(tmp_path):
    collection = vector_store.get_collection(str(tmp_path / "vector_index"))
    vector_store.index_row(
        collection,
        _row(1, subject="physics", topic="newton's laws", content="force equals mass times acceleration"),
    )
    vector_store.index_row(
        collection,
        _row(2, subject="biology", topic="photosynthesis", content="plants convert light energy into glucose"),
    )

    results = vector_store.search(collection, subject="biology", query="force acceleration")

    assert all(row["subject"] == "biology" for row in results)


def test_search_returned_dict_shape_matches_subject_topic_content_source(tmp_path):
    collection = vector_store.get_collection(str(tmp_path / "vector_index"))
    vector_store.index_row(
        collection,
        _row(1, subject="math", topic="linear equations", content="isolate the variable", source="seed"),
    )

    results = vector_store.search(collection, subject="math", query="linear equations")

    assert results[0] == {
        "subject": "math",
        "topic": "linear equations",
        "content": "isolate the variable",
        "source": "seed",
    }


def test_search_subject_match_is_case_insensitive(tmp_path):
    collection = vector_store.get_collection(str(tmp_path / "vector_index"))
    vector_store.index_row(
        collection,
        _row(1, subject="geography", topic="population pyramids", content="age and gender structure of a population"),
    )

    results = vector_store.search(collection, subject="Geography", query="population age structure")

    assert results
    assert results[0]["topic"] == "population pyramids"


def test_reindex_all_returns_the_row_count_indexed(tmp_path, empty_conn):
    _insert_row(empty_conn, subject="math", topic="algebra", content="solve for x")
    _insert_row(empty_conn, subject="biology", topic="cells", content="cell structure notes")
    collection = vector_store.get_collection(str(tmp_path / "vector_index"))

    indexed = vector_store.reindex_all(collection, empty_conn)

    assert indexed == 2
    assert collection.count() == 2


def test_reindex_all_rebuilds_from_sqlite_when_chroma_is_out_of_sync_with_it(tmp_path, empty_conn):
    row_id = _insert_row(empty_conn, subject="math", topic="algebra", content="solve for x")
    collection = vector_store.get_collection(str(tmp_path / "vector_index"))
    vector_store.reindex_all(collection, empty_conn)
    assert collection.count() == 1

    empty_conn.execute("DELETE FROM course_content WHERE id = ?", (row_id,))
    empty_conn.commit()
    _insert_row(empty_conn, subject="biology", topic="cells", content="cell structure notes")
    _insert_row(empty_conn, subject="physics", topic="newton's laws", content="force equals mass times acceleration")

    vector_store.reindex_all(collection, empty_conn)

    assert collection.count() == 2
    remaining_topics = {row["topic"] for row in collection.get(include=["metadatas"])["metadatas"]}
    assert remaining_topics == {"cells", "newton's laws"}


def test_ensure_index_is_a_no_op_when_already_in_sync(tmp_path):
    from data.db import get_connection, init_db

    db_path = tmp_path / "app.db"
    init_db(db_path)
    conn = get_connection(db_path)
    _insert_row(conn, subject="math", topic="algebra", content="solve for x")
    conn.close()

    vector_path = str(tmp_path / "vector_index")
    vector_store.ensure_index(vector_path, str(db_path))
    collection = vector_store.get_collection(vector_path)
    assert collection.count() == 1

    vector_store.ensure_index(vector_path, str(db_path))

    assert collection.count() == 1


def test_index_row_upsert_is_idempotent_on_reindex(tmp_path, empty_conn):
    _insert_row(empty_conn, subject="math", topic="algebra", content="solve for x")
    collection = vector_store.get_collection(str(tmp_path / "vector_index"))

    vector_store.reindex_all(collection, empty_conn)
    vector_store.reindex_all(collection, empty_conn)

    assert collection.count() == 1
