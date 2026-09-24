"""
Summary engine: extract structured metadata from document chunks.
Never invents party names, dates, amounts, penalties, or clauses.
"""
import re
from backend.database import get_db_connection
from backend.ai_engine import generate_text
from backend.prompts import SYSTEM_PROMPT
from backend.safety import sanitize_retrieved_context, validate_ai_output
from backend.risk_engine import analyze_risks, RISK_PATTERNS
from backend.deadline_detection import detect_deadlines
from backend.utils import safe_log


# ---------------------------------------------------------------------------
# Deterministic extractors
# ---------------------------------------------------------------------------

PARTY_PATTERNS = [
    r"(?:between|by\s+and\s+between)\s+([A-Z][A-Za-z\s]+?(?:Ltd|LLC|Inc|Corp|Company|LLP|Pvt)?\.?)\s+(?:and|&)\s+([A-Z][A-Za-z\s]+?(?:Ltd|LLC|Inc|Corp|Company|LLP|Pvt)?\.?)",
    r"(?:hereinafter\s+referred\s+to\s+as|known\s+as)\s+[\"']?([A-Z][A-Za-z\s]+)[\"']?",
]

DURATION_PATTERNS = [
    r"(?:term|duration|period)\s+(?:of|shall\s+be|is)\s+(\d+\s+(?:month|year|day|week)s?)",
    r"(?:commenc(?:es?|ing)|effective)\s+(?:from|on|date)\s+(.{0,40}?)\s+(?:and|until|through|to)\s+(.{0,40})",
]

DOC_TYPE_HINTS = {
    "Non-Disclosure Agreement": ["non-disclosure", "nda", "confidential information", "proprietary"],
    "Employment Agreement": ["employment", "employee", "employer", "salary", "wages", "hire"],
    "Service Agreement": ["service agreement", "services", "contractor", "deliverables"],
    "Lease Agreement": ["lease", "landlord", "tenant", "rent", "premises"],
    "License Agreement": ["license", "licensor", "licensee", "intellectual property", "royalty"],
    "Purchase Agreement": ["purchase", "buyer", "seller", "sale of goods", "acquisition"],
    "Partnership Agreement": ["partnership", "partners", "profit sharing", "joint venture"],
    "Loan Agreement": ["loan", "borrower", "lender", "interest rate", "repayment"],
}


def _detect_document_type(full_text: str) -> str:
    lowered = full_text.lower()
    for doc_type, keywords in DOC_TYPE_HINTS.items():
        for kw in keywords:
            if kw in lowered:
                return doc_type
    return "Legal Agreement"


def _extract_parties(full_text: str) -> list:
    parties = []
    for pat in PARTY_PATTERNS:
        matches = re.findall(pat, full_text)
        for m in matches:
            if isinstance(m, tuple):
                parties.extend([p.strip() for p in m if p.strip()])
            elif isinstance(m, str) and m.strip():
                parties.append(m.strip())
    # Deduplicate; limit to 5 names
    seen = []
    for p in parties:
        if p not in seen and len(p) > 2:
            seen.append(p)
    return seen[:5]


def _extract_duration(full_text: str) -> str:
    lowered = full_text.lower()
    for pat in DURATION_PATTERNS:
        m = re.search(pat, lowered)
        if m:
            return m.group(0)[:100]
    return ""


def _extract_important_clauses(risks: list) -> list:
    """Return top-priority risk-flagged clauses as structured list."""
    important = []
    seen = set()
    for flag in risks:
        if flag["severity"] in ("IMPORTANT", "REVIEW"):
            key = (flag.get("clause_number"), flag.get("page_number"))
            if key not in seen:
                seen.add(key)
                important.append({
                    "page": flag.get("page_number"),
                    "clause": flag.get("clause_number"),
                    "title": flag.get("clause_title"),
                    "type": flag.get("risk_type"),
                    "severity": flag.get("severity"),
                    "reason": flag.get("description"),
                })
    return important[:10]


def generate_summary(document_id: int) -> dict:
    """
    Generate a structured document summary.
    Uses deterministic extractors first, then optionally LLM for the prose summary.
    Never invents facts not found in the document.
    """
    conn = get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    chunks = conn.execute(
        "SELECT id, content, page_number, clause_number, clause_title FROM chunks WHERE document_id = ?",
        (document_id,)
    ).fetchall()
    conn.close()

    if not doc:
        return {"error": "Document not found"}

    if not chunks:
        return {
            "document_id": document_id,
            "summary": "No readable content was found in this document.",
            "key_points": [],
            "important_clauses": [],
            "deadlines": [],
            "needs_professional_review": True,
        }

    full_text = "\n".join(c["content"] for c in chunks)

    doc_type = _detect_document_type(full_text)
    parties = _extract_parties(full_text)
    duration = _extract_duration(full_text)
    risks = analyze_risks(document_id)
    deadlines = detect_deadlines(document_id)
    important_clauses = _extract_important_clauses(risks)

    # Build evidence for LLM (first 5 chunks, sanitised)
    top_chunks = [dict(c) for c in chunks[:5]]
    context = sanitize_retrieved_context(top_chunks)

    user_prompt = (
        f"Based ONLY on the following evidence extracted from the document, "
        f"write a concise 2-4 sentence summary of what this legal document is about. "
        f"Do not invent any facts. If information is absent, do not include it.\n\n"
        f"Evidence:\n{context}"
    )

    prose_summary = generate_text(SYSTEM_PROMPT, user_prompt)
    if not validate_ai_output(prose_summary):
        prose_summary = "A summary could not be safely generated. Please review the document directly."

    key_points = []
    if doc_type:
        key_points.append(f"Document type: {doc_type}")
    if parties:
        key_points.append(f"Parties involved: {', '.join(parties)}")
    if duration:
        key_points.append(f"Duration reference found: {duration}")

    return {
        "document_id": document_id,
        "document_type": doc_type,
        "parties": parties,
        "duration": duration if duration else None,
        "summary": prose_summary,
        "key_points": key_points,
        "important_clauses": important_clauses,
        "deadlines": deadlines[:10],
        "needs_professional_review": True,
    }


def get_important_clauses(document_id: int) -> list:
    """Return top review-worthy clauses based on risk severity."""
    risks = analyze_risks(document_id)
    return _extract_important_clauses(risks)
