"""
Lawyer Preparation engine for LegalEase AI.
Generates a structured Case Preparation Brief grounded strictly in document evidence
to help users prepare for a professional legal consultation.
"""
from backend.database import get_db_connection
from backend.risk_engine import analyze_risks
from backend.deadline_detection import detect_deadlines
from backend.summary import _detect_document_type
from backend.ai_engine import generate_text
from backend.prompts import SYSTEM_PROMPT
from backend.safety import detect_prompt_injection, sanitize_retrieved_context, validate_ai_output
from backend.utils import safe_log
import json


def generate_lawyer_prep(document_id: int, situation: str = "", country: str = "", region: str = "") -> dict:
    """
    Generate a Case Preparation Brief for a lawyer consultation.
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

    if situation and detect_prompt_injection(situation):
        situation = "[Potentially malicious input sanitized]"

    full_text = "\n".join(c["content"] for c in chunks)
    doc_type = _detect_document_type(full_text)

    # Gather risk flags & deadlines
    risks = analyze_risks(document_id)
    deadlines = detect_deadlines(document_id)

    important_clauses = []
    for r in risks[:5]:
        important_clauses.append({
            "title": r.get("clause_title") or r.get("risk_type"),
            "clause": r.get("clause_number"),
            "page": r.get("page_number"),
            "description": r.get("description")
        })

    important_dates = []
    for d in deadlines[:5]:
        important_dates.append({
            "deadline": d.get("deadline"),
            "context": d.get("context"),
            "page": d.get("page"),
            "clause": d.get("clause")
        })

    # Jurisdiction context
    country = country or doc["jurisdiction_country"] or ""
    region = region or doc["jurisdiction_region"] or ""

    if not country and not region:
        jurisdiction_note = "Jurisdiction is not specified. Inform your lawyer of your state/country location as legal standards vary."
    else:
        jurisdiction_note = f"Specified jurisdiction: {country} {region}".strip()

    # Use LLM to generate questions to ask, missing info, items requiring verification
    context_chunks = [dict(c) for c in chunks[:5]]
    sanitized_context = sanitize_retrieved_context(context_chunks)

    user_prompt = (
        f"You are helping a client prepare a brief for their initial consultation with a lawyer.\n"
        f"Document Type: {doc_type}\n"
        f"Client Situation: {situation or 'Reviewing agreement terms'}\n"
        f"Jurisdiction: {country} {region}\n\n"
        f"Document Evidence:\n{sanitized_context}\n\n"
        f"Provide a JSON response with:\n"
        f"1. 'questions_to_ask_lawyer': 3-5 specific, relevant questions the client should ask their lawyer.\n"
        f"2. 'missing_information': 2-3 items of information or exhibits missing from the document.\n"
        f"3. 'items_requiring_verification': 2-3 factual or legal items that require attorney verification.\n"
        f"Do NOT answer the questions yourself. Only frame the questions for the lawyer.\n\n"
        f"Respond in JSON matching:\n"
        f"{{\n"
        f'  "questions_to_ask_lawyer": ["question 1", "question 2"],\n'
        f'  "missing_information": ["item 1", "item 2"],\n'
        f'  "items_requiring_verification": ["item 1", "item 2"]\n'
        f"}}\n"
    )

    questions = [
        "What obligations appear to apply under the termination and notice clauses?",
        "Does the notice provision apply to this specific situation?",
        "Which provisions in this agreement pose the highest legal risk for my position?"
    ]
    missing_info = ["Schedules, attachments, or referenced exhibits if not attached."]
    items_verify = ["Applicable local statutory notice requirements and effective dates."]

    try:
        raw_resp = generate_text(SYSTEM_PROMPT, user_prompt)
        if validate_ai_output(raw_resp):
            parsed = json.loads(raw_resp)
            questions = parsed.get("questions_to_ask_lawyer", questions)
            missing_info = parsed.get("missing_information", missing_info)
            items_verify = parsed.get("items_requiring_verification", items_verify)
    except Exception as e:
        safe_log("error", f"Lawyer prep LLM generation failed: {e}")

    docs_to_bring = [
        f"The main document: {doc['filename']}",
        "Any amendments, addenda, or referenced exhibits",
        "Written communications (emails, letters) related to this matter",
        "Proof of payment or performance records if applicable"
    ]

    return {
        "title": "CASE PREPARATION BRIEF",
        "document_id": document_id,
        "filename": doc["filename"],
        "document_type": doc_type,
        "situation_summary": situation or f"Review of {doc['filename']} ({doc_type})",
        "documents_identified": [doc["filename"]],
        "important_clauses": important_clauses,
        "important_dates": important_dates,
        "questions_to_ask_lawyer": questions,
        "missing_information": missing_info,
        "documents_to_bring": docs_to_bring,
        "items_requiring_verification": items_verify,
        "jurisdiction_context": {
            "country": country,
            "region": region,
            "jurisdiction_note": jurisdiction_note
        },
        "professional_review_recommended": True
    }
