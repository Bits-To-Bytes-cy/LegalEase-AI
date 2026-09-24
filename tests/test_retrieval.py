import pytest
from backend.retrieval import compute_tf, compute_idf, retrieve_relevant_chunks
from backend.database import init_db, get_db_connection
from backend.app import app

def test_tf_idf_math():
    tf = compute_tf(["hello", "world", "hello"])
    assert tf["hello"] == 2/3
    assert tf["world"] == 1/3

    idf = compute_idf([["doc", "one"], ["doc", "two"]])
    assert idf["doc"] == 1.0 # smoothed idf: log10((2+1)/(2+1)) + 1
    assert idf["one"] > 1.0 # smoothed idf: log10((2+1)/(1+1)) + 1

def test_retrieve_relevant_chunks(monkeypatch):
    monkeypatch.setenv("DATABASE_URI", "sqlite:///:memory:")
    app.config['DATABASE_URI'] = "sqlite:///:memory:"
    with app.app_context():
        init_db()
        conn = get_db_connection()
        conn.execute("INSERT INTO documents (filename, file_type, status) VALUES ('test.txt', 'txt', 'completed')")
        doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("INSERT INTO chunks (document_id, content, clause_title) VALUES (?, 'apple banana', 'title1')", (doc_id,))
        conn.execute("INSERT INTO chunks (document_id, content, clause_title) VALUES (?, 'cherry dog', 'title2')", (doc_id,))
        conn.commit()
        conn.close()

        results = retrieve_relevant_chunks(doc_id, "banana")
        assert len(results) == 1
        assert "apple banana" in results[0]["content"]
