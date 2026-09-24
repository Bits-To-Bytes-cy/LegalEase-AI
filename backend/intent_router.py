import re
from backend.prompts import INTENT_CLASSIFICATION_PROMPT, SYSTEM_PROMPT
from backend.ai_engine import generate_text
from backend.utils import safe_log

# Deterministic keyword-based routing map
# Ordered list of tuples (phrase, intent) to ensure longer/more specific phrases match first
KEYWORD_RULES = [
    # Compare
    ("what changed", "COMPARE"),
    ("between these agreements", "COMPARE"),
    ("compare", "COMPARE"),
    ("difference", "COMPARE"),
    ("versus", "COMPARE"),
    ("diff", "COMPARE"),
    # Next steps
    ("next steps", "NEXT_STEPS"),
    ("next step", "NEXT_STEPS"),
    ("what should i do", "NEXT_STEPS"),
    ("what to do next", "NEXT_STEPS"),
    ("action items", "NEXT_STEPS"),
    ("what now", "NEXT_STEPS"),
    # Lawyer prep
    ("lawyer preparation", "LAWYER_PREPARATION"),
    ("lawyer prep", "LAWYER_PREPARATION"),
    ("ask my lawyer", "LAWYER_PREPARATION"),
    ("ask a lawyer", "LAWYER_PREPARATION"),
    ("prepare for lawyer", "LAWYER_PREPARATION"),
    ("lawyer brief", "LAWYER_PREPARATION"),
    ("attorney", "LAWYER_PREPARATION"),
    # Summary
    ("summary", "SUMMARY"),
    ("summarize", "SUMMARY"),
    ("what is this agreement", "SUMMARY"),
    # Explain clause
    ("explain clause", "EXPLAIN_CLAUSE"),
    ("explain", "EXPLAIN_CLAUSE"),
    # Risk
    ("risk", "RISK_ANALYSIS"),
    ("hazard", "RISK_ANALYSIS"),
    # Question
    ("question", "QUESTION"),
    ("what happens", "QUESTION"),
    ("how", "QUESTION"),
    # General info / jurisdiction
    ("information", "GENERAL_INFORMATION"),
    ("law", "GENERAL_INFORMATION"),
    ("jurisdiction", "GENERAL_INFORMATION"),
]

DOC_REQUIRED_INTENTS = {"SUMMARY", "QUESTION", "EXPLAIN_CLAUSE", "RISK_ANALYSIS", "COMPARE", "NEXT_STEPS", "LAWYER_PREPARATION"}


def detect_intent(message: str, document_present: bool = True, jurisdiction_present: bool = False):
    """
    Return a dict describing the user's intent.
    Uses deterministic keyword matching first, then falls back to LLM classification.
    """
    lowered = message.lower()
    for phrase, intent in KEYWORD_RULES:
        if phrase in lowered:
            return {
                "intent": intent,
                "reason": f"Keyword '{phrase}' matched",
                "requires_document": intent in DOC_REQUIRED_INTENTS,
                "requires_jurisdiction": intent in {"GENERAL_INFORMATION", "NEXT_STEPS", "LAWYER_PREPARATION"}
            }

    # Fallback to LLM classification
    safe_log("info", "Falling back to LLM for intent classification")
    try:
        response = generate_text(SYSTEM_PROMPT, INTENT_CLASSIFICATION_PROMPT + "\nUser: " + message)
        intent = response.strip().upper()
    except Exception as e:
        safe_log("error", f"LLM intent fallback error: {e}")
        intent = "QUESTION"

    if intent not in {"SUMMARY", "QUESTION", "EXPLAIN_CLAUSE", "RISK_ANALYSIS", "COMPARE", "NEXT_STEPS", "LAWYER_PREPARATION", "GENERAL_INFORMATION"}:
        intent = "GENERAL_INFORMATION"

    return {
        "intent": intent,
        "reason": "LLM classification",
        "requires_document": intent in DOC_REQUIRED_INTENTS,
        "requires_jurisdiction": intent in {"GENERAL_INFORMATION", "NEXT_STEPS", "LAWYER_PREPARATION"}
    }
