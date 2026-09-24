"""
Deadline detection: find time-bound phrases in document chunks.
Never converts vague language into specific calendar dates unless the document provides them.
"""
import re
from backend.database import get_db_connection
from backend.utils import safe_log

DEADLINE_PATTERNS = [
    r"within\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|thirty|sixty|ninety)\s+(?:business\s+)?(?:day|week|month|year)s?",
    r"no\s+later\s+than\s+.{0,60}",
    r"(?:before|prior\s+to)\s+.{0,60}",
    r"notice\s+period\s+of\s+.{0,60}",
    r"renewal\s+date",
    r"payment\s+(?:is\s+)?due\s+.{0,60}",
    r"deadline\s+(?:is|of|for)?\s*.{0,60}",
    r"by\s+(?:the\s+)?(?:end|close)\s+of\s+.{0,60}",
    r"(?:thirty|sixty|ninety|\d+)\s+days?\s+(?:notice|prior|before|after)",
]


def detect_deadlines(document_id: int) -> list:
    """
    Scan all chunks of a document for deadline-related phrases.
    Returns a list of deadline dicts with context, page and clause.
    """
    conn = get_db_connection()
    chunks = conn.execute(
        "SELECT id, content, page_number, clause_number, clause_title FROM chunks WHERE document_id = ?",
        (document_id,)
    ).fetchall()
    conn.close()

    deadlines = []
    for chunk in chunks:
        text = chunk["content"]
        lowered = text.lower()
        for pat in DEADLINE_PATTERNS:
            for match in re.finditer(pat, lowered):
                # Extract the matched span with a bit of surrounding context
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 80)
                context = text[start:end].strip()
                matched_text = match.group(0)
                # Avoid duplicate entries for same chunk + same match
                entry = {
                    "deadline": matched_text,
                    "context": context,
                    "page": chunk["page_number"],
                    "clause": chunk["clause_number"],
                    "clause_title": chunk["clause_title"],
                    "chunk_id": chunk["id"],
                }
                if entry not in deadlines:
                    deadlines.append(entry)

    safe_log("info", f"Deadline detection for document {document_id}: {len(deadlines)} found")
    return deadlines
