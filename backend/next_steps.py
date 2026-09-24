"""
Next-Step Guidance engine for LegalEase AI.
Generates safe, structured practical next steps based on document evidence and user situation.
Never provides definitive legal advice or guarantees legal outcomes.
"""
from backend.database import get_db_connection
from backend.retrieval import retrieve_relevant_chunks
from backend.ai_engine import generate_text
from backend.prompts import SYSTEM_PROMPT
from backend.safety import detect_prompt_injection, sanitize_retrieved_context, validate_ai_output
from backend.utils import safe_log
import json


def generate_next_steps(document_id: int, situation: str = "", country: str = "", region: str = "") -> dict:
    """
    Generate structured next-step guidance for a given document and user situation.
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

    # Prompt injection check on situation input
    if situation and detect_prompt_injection(situation):
        situation = "[Potentially malicious input sanitized]"

    # Retrieve relevant evidence if situation query provided, or use top chunks
    if situation:
        rel_chunks = retrieve_relevant_chunks(document_id, situation, top_k=5)
        if not rel_chunks:
            rel_chunks = [dict(c) for c in chunks[:5]]
    else:
        rel_chunks = [dict(c) for c in chunks[:5]]

    sanitized_context = sanitize_retrieved_context(rel_chunks)

    # Jurisdiction handling
    jurisdiction_note = ""
    country = country or doc["jurisdiction_country"] or ""
    region = region or doc["jurisdiction_region"] or ""

    if not country and not region:
        jurisdiction_note = "Jurisdiction context is not specified. Legal requirements and deadlines vary significantly by country and state/region."
    else:
        jurisdiction_note = f"Applicable jurisdiction context: {country} {region}".strip()

    user_prompt = (
        f"You are providing safe legal information next-step guidance to a user.\n"
        f"User Situation / Question: {situation or 'General document next steps'}\n"
        f"Jurisdiction Context: {country} {region}\n\n"
        f"Document Evidence:\n{sanitized_context}\n\n"
        f"INSTRUCTIONS:\n"
        f"- Do NOT provide definitive legal advice or legal guarantees.\n"
        f"- Do NOT tell the user they will win or lose.\n"
        f"- Base facts strictly on the document evidence provided.\n"
        f"- Prefer framing phrases: 'The document states...', 'You may want to check...', 'Consider discussing...', 'Verify local rules...'\n\n"
        f"Respond ONLY in valid JSON matching this exact structure:\n"
        f"{{\n"
        f'  "document_facts": ["fact 1", "fact 2"],\n'
        f'  "things_to_check": ["check 1", "check 2"],\n'
        f'  "questions_to_consider": ["question 1", "question 2"],\n'
        f'  "documents_to_preserve": ["document 1", "document 2"]\n'
        f"}}\n"
    )

    doc_facts = []
    things_check = ["Review key dates and notice windows in the agreement."]
    questions_consider = ["What specific timeline applies to your situation?"]
    docs_preserve = ["Keep a copy of this agreement and related written communications."]

    try:
        raw_resp = generate_text(SYSTEM_PROMPT, user_prompt)
        if validate_ai_output(raw_resp):
            parsed = json.loads(raw_resp)
            doc_facts = parsed.get("document_facts", doc_facts)
            things_check = parsed.get("things_to_check", things_check)
            questions_consider = parsed.get("questions_to_consider", questions_consider)
            docs_preserve = parsed.get("documents_to_preserve", docs_preserve)
    except Exception as e:
        safe_log("error", f"Next steps LLM generation failed: {e}")

    # Fallback deterministic facts if LLM didn't return any
    if not doc_facts and rel_chunks:
        for c in rel_chunks[:3]:
            title = c.get("clause_title") or f"Clause {c.get('clause_number') or c.get('id')}"
            snippet = c.get("content", "")[:120].strip()
            doc_facts.append(f"The document states in {title}: \"{snippet}...\"")

    return {
        "document_id": document_id,
        "situation": situation or "General next steps for document",
        "document_facts": doc_facts,
        "things_to_check": things_check,
        "questions_to_consider": questions_consider,
        "documents_to_preserve": docs_preserve,
        "jurisdiction_context": {
            "country": country,
            "region": region,
            "jurisdiction_note": jurisdiction_note
        },
        "professional_review_recommended": True
    }
