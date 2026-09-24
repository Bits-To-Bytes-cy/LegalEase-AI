import pytest
from backend.document_processor import format_chunks

def test_format_chunks():
    text = "1. Definitions\nThis is a definition.\nSECTION 2\nThis is another clause."
    chunks = format_chunks(text, "txt", 1)

    assert len(chunks) == 2
    assert chunks[0]["clause_title"] == "Definitions"
    assert "This is a definition" in chunks[0]["content"]

    assert chunks[1]["clause_title"] == "SECTION 2"
    assert "another clause" in chunks[1]["content"]
