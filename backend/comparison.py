"""
Two-document comparison engine.
Uses deterministic comparison logic first (clause number, clause title, text similarity/diff),
then optionally uses the LLM to explain detected differences strictly grounded in evidence.
"""
import difflib
import re
from backend.database import get_db_connection
from backend.ai_engine import generate_text
from backend.prompts import SYSTEM_PROMPT
from backend.safety import validate_ai_output
from backend.utils import safe_log


def _normalize_title(title: str) -> str:
    if not title:
        return ""
    # Lowercase, strip punctuation and extra whitespace
    clean = re.sub(r"[^\w\s]", "", title.lower()).strip()
    return clean


def _normalize_num(num) -> str:
    if num is None:
        return ""
    return str(num).strip().lower()


def compare_documents(doc_a_id: int, doc_b_id: int) -> dict:
    """
    Compare two documents deterministically using SQLite chunks.
    Classifies clause differences into UNCHANGED, MODIFIED, ADDED, REMOVED.
    """
    conn = get_db_connection()
    doc_a = conn.execute("SELECT id, filename FROM documents WHERE id = ?", (doc_a_id,)).fetchone()
    doc_b = conn.execute("SELECT id, filename FROM documents WHERE id = ?", (doc_b_id,)).fetchone()

    if not doc_a or not doc_b:
        conn.close()
        return {"error": "One or both documents not found"}

    chunks_a = [dict(c) for c in conn.execute(
        "SELECT id, page_number, clause_number, clause_title, content FROM chunks WHERE document_id = ? ORDER BY id",
        (doc_a_id,)
    ).fetchall()]

    chunks_b = [dict(c) for c in conn.execute(
        "SELECT id, page_number, clause_number, clause_title, content FROM chunks WHERE document_id = ? ORDER BY id",
        (doc_b_id,)
    ).fetchall()]

    conn.close()

    matched_b_ids = set()
    pairs = []  # (chunk_a, chunk_b)

    # 1. Match by exact title or clause_number
    for ca in chunks_a:
        title_a = _normalize_title(ca.get("clause_title"))
        num_a = _normalize_num(ca.get("clause_number"))
        matched_cb = None

        # Priority A: Clause number match
        if num_a:
            for cb in chunks_b:
                if cb["id"] in matched_b_ids:
                    continue
                num_b = _normalize_num(cb.get("clause_number"))
                if num_a == num_b and num_a != "":
                    matched_cb = cb
                    break

        # Priority B: Clause title match
        if not matched_cb and title_a:
            for cb in chunks_b:
                if cb["id"] in matched_b_ids:
                    continue
                title_b = _normalize_title(cb.get("clause_title"))
                if title_a == title_b and title_a != "":
                    matched_cb = cb
                    break

        if matched_cb:
            matched_b_ids.add(matched_cb["id"])
            pairs.append((ca, matched_cb))
        else:
            pairs.append((ca, None))

    # Chunks in B that were not matched to any chunk in A
    for cb in chunks_b:
        if cb["id"] not in matched_b_ids:
            pairs.append((None, cb))

    changes = []
    summary = {
        "total_compared": len(pairs),
        "modified": 0,
        "added": 0,
        "removed": 0,
        "unchanged": 0
    }

    for ca, cb in pairs:
        if ca is not None and cb is not None:
            text_a = ca["content"].strip()
            text_b = cb["content"].strip()

            if text_a == text_b:
                status = "UNCHANGED"
                summary["unchanged"] += 1
                explanation = "The clause text is identical in both documents."
            else:
                status = "MODIFIED"
                summary["modified"] += 1
                explanation = _generate_explanation(ca, cb, text_a, text_b)

            clause_identifier = (
                ca.get("clause_number")
                or cb.get("clause_number")
                or ca.get("clause_title")
                or cb.get("clause_title")
                or f"Clause {ca['id']}"
            )
            title = ca.get("clause_title") or cb.get("clause_title") or ""

            changes.append({
                "status": status,
                "clause": str(clause_identifier),
                "clause_title": title,
                "old_text": text_a,
                "new_text": text_b,
                "explanation": explanation,
                "document_a_page": ca["page_number"],
                "document_b_page": cb["page_number"]
            })

        elif ca is not None and cb is None:
            status = "REMOVED"
            summary["removed"] += 1
            clause_identifier = ca.get("clause_number") or ca.get("clause_title") or f"Clause {ca['id']}"
            changes.append({
                "status": status,
                "clause": str(clause_identifier),
                "clause_title": ca.get("clause_title") or "",
                "old_text": ca["content"].strip(),
                "new_text": "",
                "explanation": "This clause appears in Document A but was not found in Document B.",
                "document_a_page": ca["page_number"],
                "document_b_page": None
            })

        elif ca is None and cb is not None:
            status = "ADDED"
            summary["added"] += 1
            clause_identifier = cb.get("clause_number") or cb.get("clause_title") or f"Clause {cb['id']}"
            changes.append({
                "status": status,
                "clause": str(clause_identifier),
                "clause_title": cb.get("clause_title") or "",
                "old_text": "",
                "new_text": cb["content"].strip(),
                "explanation": "This clause appears in Document B but was not found in Document A.",
                "document_a_page": None,
                "document_b_page": cb["page_number"]
            })

    safe_log("info", f"Compared doc {doc_a_id} and {doc_b_id}: {summary}")
    return {
        "document_a_id": doc_a_id,
        "document_b_id": doc_b_id,
        "document_a_filename": doc_a["filename"],
        "document_b_filename": doc_b["filename"],
        "summary": summary,
        "changes": changes
    }


def _generate_explanation(ca: dict, cb: dict, text_a: str, text_b: str) -> str:
    """Generate concise factual explanation of text change between ca and cb."""
    # Simple deterministic diff note first
    a_words = text_a.split()
    b_words = text_b.split()
    diff = list(difflib.ndiff(a_words, b_words))
    added = [w[2:] for w in diff if w.startswith("+ ")]
    removed = [w[2:] for w in diff if w.startswith("- ")]

    det_note = f"Text modified: {len(removed)} word(s) removed, {len(added)} word(s) added."

    # Use LLM for plain-language explanation of already-detected difference
    user_prompt = (
        f"Compare these two specific text versions of a legal clause and explain what changed in 1-2 factual sentences.\n"
        f"Do NOT invent differences. Ground your explanation ONLY in the text provided.\n\n"
        f"Document A:\n{text_a}\n\n"
        f"Document B:\n{text_b}"
    )

    try:
        explanation = generate_text(SYSTEM_PROMPT, user_prompt)
        if validate_ai_output(explanation) and explanation.strip():
            return explanation.strip()
    except Exception as e:
        safe_log("error", f"LLM comparison explanation failed: {e}")

    return det_note
