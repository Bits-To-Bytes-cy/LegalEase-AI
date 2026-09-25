"""
Risk engine: deterministic pattern matching for legal risk categories.
All flags are advisory ("may deserve review"), never legal conclusions.
"""
import re
from backend.database import get_db_connection
from backend.utils import safe_log

# ---------------------------------------------------------------------------
# Pattern definitions
# Each entry: (risk_type, severity, patterns, description_template)
# ---------------------------------------------------------------------------
RISK_PATTERNS = [
    (
        "AUTO_RENEWAL",
        "IMPORTANT",
        [r"auto(?:matic(?:ally)?)?[\s-]renew", r"renew(?:s|ed|al)?\s+automatically", r"unless.{0,40}terminat"],
        "This clause may create an automatic renewal obligation. Review notice periods carefully."
    ),
    (
        "TERMINATION",
        "REVIEW",
        [r"terminat(?:e|ion|ed)", r"cancel(?:lation)?", r"end\s+of\s+(?:the\s+)?agreement"],
        "This clause relates to termination conditions that may deserve review."
    ),
    (
        "PENALTY",
        "IMPORTANT",
        [r"penalt(?:y|ies)", r"liquidated\s+damage", r"late\s+fee", r"fine\b"],
        "This clause describes a financial penalty or fee that creates a broad obligation."
    ),
    (
        "LIABILITY",
        "REVIEW",
        [r"liabilit(?:y|ies)", r"limit(?:ation|ing)\s+of\s+liability", r"not\s+liable", r"exclud(?:e|es|ing)\s+liabilit"],
        "This clause places or limits liability in a way that may deserve review."
    ),
    (
        "INDEMNITY",
        "IMPORTANT",
        [r"indemni(?:fy|fication|ty)", r"hold\s+harmless", r"defend\s+and\s+indemni"],
        "This clause creates an indemnification obligation that may create broad financial exposure."
    ),
    (
        "PAYMENT",
        "REVIEW",
        [r"payment\s+due", r"invoice(?:d)?", r"fee(?:s)?\s+payable", r"consideration\s+of", r"\$\d+", r"remuneration"],
        "This clause describes financial payment terms that should be reviewed."
    ),
    (
        "CONFIDENTIALITY",
        "REVIEW",
        [r"confidential(?:ity|ial)?", r"non[- ]disclosure", r"proprietary\s+information", r"trade\s+secret"],
        "This clause creates confidentiality obligations that may restrict disclosure."
    ),
    (
        "DATA_PRIVACY",
        "REVIEW",
        [r"personal\s+data", r"data\s+protect(?:ion|ed)", r"privacy\s+polic(?:y|ies)", r"GDPR", r"process(?:ing)?\s+(?:of\s+)?data"],
        "This clause relates to data privacy or processing that may impose compliance obligations."
    ),
    (
        "NON_COMPETE",
        "IMPORTANT",
        [r"non[- ]compet(?:e|ition|itive)", r"not\s+to\s+compete", r"restrict(?:ed|ion)\s+(?:from\s+)?(?:working|engaging)"],
        "This clause may restrict future business activities and deserves careful review."
    ),
    (
        "JURISDICTION",
        "INFO",
        [r"govern(?:ing|ed)\s+by\s+(?:the\s+)?law", r"jurisdiction\s+of", r"courts?\s+of", r"arbitration\s+in"],
        "This clause specifies governing law or jurisdiction that is worth confirming."
    ),
    (
        "DEADLINE",
        "REVIEW",
        [r"within\s+\d+\s+(?:day|week|month|year)", r"no\s+later\s+than", r"prior\s+to", r"notice\s+period", r"deadline"],
        "This clause contains a time-bound obligation or deadline that requires attention."
    ),
    (
        "DISPUTE_RESOLUTION",
        "INFO",
        [r"dispute(?:s)?\s+(?:shall|will|to)\s+be\s+(?:resolved|settled)", r"arbitrat(?:ion|e|or)", r"mediat(?:ion|e|or)"],
        "This clause defines how disputes will be resolved, affecting your legal options."
    ),
]


def _scan_chunk(chunk_text: str, chunk_id: int, page_number, clause_number, clause_title: str):
    """Scan a single chunk against all risk patterns. Returns list of risk flags."""
    flags = []
    lowered = chunk_text.lower()
    seen_types = set()
    for risk_type, severity, patterns, description in RISK_PATTERNS:
        if risk_type in seen_types:
            continue
        for pat in patterns:
            if re.search(pat, lowered):
                # Grab a short evidence snippet (first 200 chars of chunk)
                evidence = chunk_text[:200].strip()
                flags.append({
                    "risk_type": risk_type,
                    "severity": severity,
                    "description": description,
                    "evidence": evidence,
                    "page_number": page_number,
                    "clause_number": clause_number,
                    "clause_title": clause_title,
                    "chunk_id": chunk_id,
                })
                seen_types.add(risk_type)
                break
    return flags


def analyze_risks(document_id: int) -> list:
    """
    Run deterministic risk detection across all chunks of a document.
    Returns a list of risk flag dicts ordered by severity (IMPORTANT first).
    """
    conn = get_db_connection()
    chunks = conn.execute(
        "SELECT id, content, page_number, clause_number, clause_title FROM chunks WHERE document_id = ?",
        (document_id,)
    ).fetchall()
    conn.close()

    if not chunks:
        safe_log("info", f"No chunks found for document {document_id} during risk analysis")
        return []

    all_flags = []
    for chunk in chunks:
        flags = _scan_chunk(
            chunk["content"],
            chunk["id"],
            chunk["page_number"],
            chunk["clause_number"],
            chunk["clause_title"],
        )
        all_flags.extend(flags)

    # ---------------------------------------------------------------------------
    # Deduplication – two-pass approach
    #
    # Problem the old approach missed:
    #   The same logical clause can appear twice because overlapping/continuation
    #   chunks may carry (a) the real clause number + title on one chunk and
    #   (b) no clause number (None) with a synonym or truncated title on another.
    #   E.g.  chunk A: clause_number="9.",  clause_title="INDEMNIFICATION"
    #         chunk B: clause_number=None,  clause_title="INDEMNITY"
    #   Old key was either the number or the title, never both, so A and B got
    #   different keys and both survived.
    #
    # Fix:
    #   Pass 1 – map every flag to a canonical (risk_type, canonical_title) key
    #            using a small synonym table that covers known close variants.
    #   Pass 2 – for each canonical bucket keep only the single best flag:
    #            prefer an entry with a real clause_number over a None entry.
    #            If all entries in the bucket are numbered, keep the first.
    # ---------------------------------------------------------------------------

    # Synonym table: maps any variant (lowercased, stripped) to a canonical form.
    # Only add pairs that are genuinely equivalent legal concepts.
    _TITLE_SYNONYMS = {
        "indemnity":               "indemnification",
        "indemnification":         "indemnification",
        "indemnify":               "indemnification",
        "termination":             "termination",
        "end of agreement":        "termination",
        "cancellation":            "termination",
        "limitation of liability": "limitation of liability",
        "liability":               "liability",
        "confidential":            "confidentiality",
        "confidentiality":         "confidentiality",
        "non-disclosure":          "confidentiality",
        "non disclosure":          "confidentiality",
    }

    def _canonical_title(raw_title: str) -> str:
        """Return a canonical, normalised version of a clause title for dedup purposes."""
        if not raw_title:
            return ""
        # Strip, lowercase, collapse internal whitespace
        t = " ".join(raw_title.strip().lower().split())
        # Check synonym table for an exact match first
        if t in _TITLE_SYNONYMS:
            return _TITLE_SYNONYMS[t]
        # Check if any synonym key is *contained* in the title (e.g. "9. INDEMNIFICATION")
        for variant, canonical in _TITLE_SYNONYMS.items():
            if variant in t:
                return canonical
        return t

    # Pass 1: group flags by (risk_type, canonical_title)
    from collections import OrderedDict
    buckets: dict = OrderedDict()
    for flag in all_flags:
        raw_title = flag.get("clause_title") or ""
        canon = _canonical_title(raw_title)
        bucket_key = (flag["risk_type"], canon)
        if bucket_key not in buckets:
            buckets[bucket_key] = []
        buckets[bucket_key].append(flag)

    # Pass 2: from each bucket pick the best representative
    deduped_flags = []
    for bucket_flags in buckets.values():
        # Prefer a flag that has a real clause_number over one that does not
        numbered = [f for f in bucket_flags if f.get("clause_number")]
        best = numbered[0] if numbered else bucket_flags[0]
        deduped_flags.append(best)

    # Pass 3: suppress orphan untitled flags.
    # A flag coming from a continuation chunk with no clause_title AND no clause_number
    # (i.e. it fell into the empty-canonical-title bucket) is almost always part of a
    # preceding named clause. If any other flag with the SAME risk_type already has a
    # real clause title/number, discard the orphan — it is not a separate clause.
    titled_risk_types = {
        f["risk_type"]
        for f in deduped_flags
        if f.get("clause_title") or f.get("clause_number")
    }
    deduped_flags = [
        f for f in deduped_flags
        if (f.get("clause_title") or f.get("clause_number"))
        or f["risk_type"] not in titled_risk_types
    ]

    # Order: IMPORTANT > REVIEW > INFO
    order = {"IMPORTANT": 0, "REVIEW": 1, "INFO": 2}
    deduped_flags.sort(key=lambda f: order.get(f["severity"], 3))
    safe_log("info", f"Risk analysis for document {document_id}: {len(deduped_flags)} flags found (after deduplication)")
    return deduped_flags

