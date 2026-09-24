"""
Consistency detection: look for potential contradictions between clauses.
Results are framed as possible inconsistencies, never as legal conclusions.
"""
import re
from backend.database import get_db_connection
from backend.utils import safe_log


def _extract_number(text: str):
    """Extract the first number (incl. spelled-out small numbers) from text."""
    spelled = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "fourteen": 14, "fifteen": 15, "thirty": 30, "sixty": 60, "ninety": 90,
        "twelve": 12, "twenty": 20,
    }
    # Try numeric first
    m = re.search(r"\d+", text)
    if m:
        return int(m.group(0))
    # Fall back to spelled
    lowered = text.lower()
    for word, val in spelled.items():
        if word in lowered:
            return val
    return None


def _find_values_in_chunks(chunks, patterns):
    """
    For each pattern, find matching chunks and extract a numeric value if present.
    Returns list of (value, chunk) tuples.
    """
    results = []
    for chunk in chunks:
        for pat in patterns:
            m = re.search(pat, chunk["content"].lower())
            if m:
                val = _extract_number(m.group(0))
                results.append((val, chunk, m.group(0)))
                break  # one match per chunk per pattern group
    return results


DEADLINE_PATS = [
    r"(?:payment\s+)?due\s+within\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|fourteen|fifteen|thirty|sixty|ninety)\s+days?",
    r"within\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|fourteen|fifteen|thirty|sixty|ninety)\s+days?\s+(?:of|from|after)",
]

DURATION_PATS = [
    r"(?:term|duration|period)\s+(?:of|shall\s+be|is)\s+(\d+|twelve|twenty|twenty[- ]four)\s+months?",
    r"(?:term|duration|period)\s+(?:of|shall\s+be|is)\s+(\d+|one|two|three)\s+years?",
]

AMOUNT_PATS = [
    r"\$\s*(\d[\d,]*(?:\.\d{2})?)",
    r"(\d[\d,]*(?:\.\d{2})?)\s+(?:USD|INR|EUR|GBP)",
]


def check_consistency(document_id: int) -> list:
    """
    Detect potential inconsistencies across clauses: deadlines, durations, amounts.
    Returns a list of inconsistency report dicts.
    """
    conn = get_db_connection()
    chunks = conn.execute(
        "SELECT id, content, page_number, clause_number, clause_title FROM chunks WHERE document_id = ?",
        (document_id,)
    ).fetchall()
    conn.close()

    if not chunks:
        return []

    inconsistencies = []

    # --- Check 1: conflicting day deadlines ---
    deadline_hits = _find_values_in_chunks(chunks, DEADLINE_PATS)
    if len(deadline_hits) > 1:
        unique_values = set(h[0] for h in deadline_hits if h[0] is not None)
        if len(unique_values) > 1:
            clause_ids = [str(h[1]["clause_number"] or h[1]["id"]) for h in deadline_hits]
            inconsistencies.append({
                "type": "POTENTIAL_INCONSISTENCY",
                "severity": "IMPORTANT",
                "category": "DEADLINE",
                "clauses": clause_ids,
                "description": f"The document appears to contain different deadline periods ({', '.join(str(v)+' days' for v in sorted(unique_values))}). These provisions may be inconsistent.",
                "action": "Verify which provision applies and seek professional clarification.",
                "evidence": [{"matched": h[2], "clause": h[1]["clause_number"], "page": h[1]["page_number"]} for h in deadline_hits],
            })

    # --- Check 2: conflicting durations ---
    duration_hits = _find_values_in_chunks(chunks, DURATION_PATS)
    if len(duration_hits) > 1:
        unique_values = set(h[0] for h in duration_hits if h[0] is not None)
        if len(unique_values) > 1:
            clause_ids = [str(h[1]["clause_number"] or h[1]["id"]) for h in duration_hits]
            inconsistencies.append({
                "type": "POTENTIAL_INCONSISTENCY",
                "severity": "IMPORTANT",
                "category": "DURATION",
                "clauses": clause_ids,
                "description": f"The agreement duration appears to be stated differently in multiple clauses ({', '.join(str(v) for v in sorted(unique_values))}). These provisions may be inconsistent.",
                "action": "Verify which duration provision controls.",
                "evidence": [{"matched": h[2], "clause": h[1]["clause_number"], "page": h[1]["page_number"]} for h in duration_hits],
            })

    safe_log("info", f"Consistency check for document {document_id}: {len(inconsistencies)} issues found")
    return inconsistencies
