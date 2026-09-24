"""
Clause explanation: returns plain-language explanation of a specific chunk.
Uses the LLM but stays strictly grounded to the retrieved chunk text.
"""
from backend.database import get_db_connection
from backend.ai_engine import generate_text
from backend.prompts import SYSTEM_PROMPT
from backend.safety import sanitize_retrieved_context, validate_ai_output
from backend.utils import safe_log


def explain_clause(chunk_id: int) -> dict:
    """
    Fetch a chunk by ID and return a plain-language explanation.
    Never invents information not present in the original chunk text.
    """
    conn = get_db_connection()
    chunk = conn.execute(
        "SELECT id, document_id, content, page_number, clause_number, clause_title FROM chunks WHERE id = ?",
        (chunk_id,)
    ).fetchone()
    conn.close()

    if not chunk:
        return {"error": "Clause not found"}

    original_text = chunk["content"]
    context = sanitize_retrieved_context([dict(chunk)])

    user_prompt = (
        f"You are explaining a legal clause to a non-expert.\n\n"
        f"Using ONLY the evidence below, provide:\n"
        f"1. A plain-language explanation of what this clause means.\n"
        f"2. Why this clause may be important to the reader.\n"
        f"Do not invent anything not stated in the clause. "
        f"Do not call it illegal, invalid, or unenforceable unless authoritative evidence is provided.\n\n"
        f"Evidence:\n{context}\n\n"
        f"Respond in JSON format:\n"
        f"{{\"plain_language\": \"...\", \"why_it_matters\": \"...\"}}"
    )

    raw = generate_text(SYSTEM_PROMPT, user_prompt)

    plain_language = ""
    why_it_matters = ""

    if validate_ai_output(raw):
        try:
            import json
            parsed = json.loads(raw)
            plain_language = parsed.get("plain_language", "")
            why_it_matters = parsed.get("why_it_matters", "")
        except Exception:
            # If LLM didn't return valid JSON, use the raw text as plain_language
            plain_language = raw[:500] if raw else ""
            why_it_matters = ""
    else:
        plain_language = "The explanation could not be safely generated. Please review the clause text directly."
        why_it_matters = "Professional review is recommended for this clause."

    return {
        "original_text": original_text,
        "plain_language": plain_language,
        "why_it_matters": why_it_matters,
        "source": {
            "chunk_id": chunk["id"],
            "page": chunk["page_number"],
            "clause": chunk["clause_number"],
            "title": chunk["clause_title"],
        },
        "professional_review_recommended": True,
    }
