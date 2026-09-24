import re
from backend.utils import safe_log

# Simple heuristic to detect prompt injection attempts in document text.
# Looks for phrases that try to override system behavior.
INJECTION_PATTERNS = [
    r"ignore all previous instructions",
    r"disregard system prompts",
    r"reveal (the )?api ?key",
    r"reveal (your |the )?system prompt",
    r"execute .*code",
    r"run .*script",
]

def detect_prompt_injection(text: str) -> bool:
    """Return True if the text appears to contain a prompt injection attempt.
    The function is deliberately permissive – it flags only obvious patterns.
    """
    lowered = text.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, lowered):
            safe_log("warning", f"Prompt injection pattern detected: {pat}")
            return True
    return False

def sanitize_retrieved_context(chunks):
    """Prepare retrieved chunks for LLM consumption.
    Each chunk is turned into a string with a clear marker that it is evidence.
    The function does NOT strip legal content – it only formats it safely.
    """
    sanitized = []
    for chunk in chunks:
        # Ensure we include identifiers for traceability
        header = f"[Evidence] Chunk ID: {chunk.get('id')}, Page: {chunk.get('page_number')}, Clause: {chunk.get('clause_number') or 'N/A'}, Title: {chunk.get('clause_title') or 'N/A'}"
        content = chunk.get('content', '')
        sanitized.append(f"{header}\n{content}")
    return "\n\n".join(sanitized)

def validate_ai_output(output: str) -> bool:
    """Validate that the LLM output does not contain disallowed content.
    Returns True if the output is considered safe, False otherwise.
    """
    if not output:
        return False
    lowered = output.lower()
    # Disallowed patterns: leaking keys, environment vars, system prompts, guarantees, fabricated citations
    disallowed = [
        r"sk-\w{20,}",  # typical OpenAI key pattern
        r"(reveal|show|display).{0,10}api[_-]?key",
        r"(reveal|show|display).{0,10}environment variable",
        r"(reveal|show|display).{0,10}system prompt",
        r"i guarantee that you will",
        r"100% chance of winning",
        r"definitely legal",
        r"definitely illegal",
        r"fabricated citation",
        r"\[fake citation\]",
    ]
    for pat in disallowed:
        if re.search(pat, lowered):
            safe_log("error", f"Disallowed content detected in LLM output: pattern {pat}")
            return False
    return True
