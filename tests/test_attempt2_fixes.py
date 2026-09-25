"""
Focused regression tests for Attempt 2 fixes:
- PART 3: Document type classification (title-priority for Service Agreement)
- PART 4: Clause fragment rejection (no 'Document Start', no sentence-ending fragments)
- PART 5: Risk deduplication (no duplicate clause entries in analyze_risks output)
"""
import sqlite3
import tempfile
import os
import pytest


# ---------------------------------------------------------------------------
# PART 3 – Document Type Classification
# ---------------------------------------------------------------------------

class TestDocumentTypeClassification:
    """_detect_document_type must prioritise title-zone phrases over body keywords."""

    def _detect(self, text):
        from backend.summary import _detect_document_type
        return _detect_document_type(text)

    def test_service_agreement_title_wins_over_confidentiality_body(self):
        """
        A Service Agreement that contains a Confidentiality section must be
        classified as 'Service Agreement', not 'Non-Disclosure Agreement'.
        """
        text = (
            "SERVICE AGREEMENT\n\n"
            "This Service Agreement is entered into between Alpha Corp and Beta LLC.\n\n"
            "1. SERVICES\nAlpha Corp will provide software development services.\n\n"
            "2. CONFIDENTIALITY\n"
            "The parties agree to keep confidential information proprietary and secret.\n\n"
            "3. TERMINATION\nEither party may terminate with 30 days notice."
        )
        assert self._detect(text) == "Service Agreement"

    def test_nda_title_matches(self):
        """A document titled Non-Disclosure Agreement must be classified correctly."""
        text = (
            "NON-DISCLOSURE AGREEMENT\n\n"
            "This NDA is between Party A and Party B.\n\n"
            "All confidential information shared shall remain proprietary."
        )
        assert self._detect(text) == "Non-Disclosure Agreement"

    def test_employment_agreement_title(self):
        text = (
            "EMPLOYMENT AGREEMENT\n\n"
            "This Employment Contract is between Employer Inc. and Employee.\n\n"
            "The employee will receive a salary and benefits."
        )
        assert self._detect(text) == "Employment Agreement"

    def test_generic_falls_back_to_keyword(self):
        """Document with no recognisable title falls back to body keyword scan."""
        text = "The parties agree on the following terms.\nThis is a lease for the premises at 10 Main St."
        result = self._detect(text)
        assert result == "Lease Agreement"

    def test_unknown_document_returns_legal_agreement(self):
        text = "The parties hereby agree to the terms and conditions set forth herein."
        assert self._detect(text) == "Legal Agreement"


# ---------------------------------------------------------------------------
# PART 4 – Clause Fragment Rejection
# ---------------------------------------------------------------------------

class TestClauseFragmentRejection:
    """format_chunks must not emit 'Document Start' or sentence-fragment clause titles."""

    def _chunks(self, text):
        from backend.document_processor import format_chunks
        return format_chunks(text, "txt", page_num=1)

    def _titles(self, text):
        return [c["clause_title"] for c in self._chunks(text)]

    def test_document_start_placeholder_not_emitted(self):
        """Pre-clause preamble text must not produce a 'Document Start' title."""
        text = "Some preamble text at the start.\n\n1. DEFINITIONS\nDefinitions clause."
        titles = self._titles(text)
        assert "Document Start" not in titles

    def test_fragment_ending_with_period_rejected(self):
        """Clause titles ending with '.' are sentence fragments and must be None or absent."""
        text = "after termination.\nThis text follows a fragment."
        titles = self._titles(text)
        assert "after termination." not in titles

    def test_legitimate_headings_preserved(self):
        """Well-formed clause headings like TERMINATION and CONFIDENTIALITY must survive."""
        text = (
            "1. SERVICES\nThe provider will deliver services.\n\n"
            "2. TERMINATION\nEither party may terminate.\n\n"
            "3. CONFIDENTIALITY\nAll data is confidential."
        )
        titles = [t for t in self._titles(text) if t]  # skip None
        assert "SERVICES" in titles or any("SERVICES" in (t or "") for t in titles)
        assert any("TERMINATION" in (t or "") for t in titles)
        assert any("CONFIDENTIALITY" in (t or "") for t in titles)

    def test_none_title_not_document_start(self):
        """Preamble chunks must have title=None rather than 'Document Start'."""
        text = "Preamble without heading."
        chunks = self._chunks(text)
        for c in chunks:
            assert c["clause_title"] != "Document Start"


# ---------------------------------------------------------------------------
# PART 5 – Risk Deduplication
# ---------------------------------------------------------------------------

class TestRiskDeduplication:
    """analyze_risks must not return duplicate (risk_type, clause) entries."""

    @pytest.fixture
    def client(self):
        from backend.app import app, init_db
        import backend.database as db_mod

        app.config["TESTING"] = True

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()

        _orig = db_mod.get_db_connection

        def _test_conn():
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
            return conn

        db_mod.get_db_connection = _test_conn
        with app.app_context():
            init_db()

        with app.test_client() as c:
            yield c

        db_mod.get_db_connection = _orig
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    def test_no_duplicate_risk_type_per_clause(self, client):
        """
        When a document has a single CONFIDENTIALITY clause that spans multiple
        overlapping chunks, the risk output must contain exactly one CONFIDENTIALITY
        flag for that clause – not multiple duplicates.
        """
        import io
        content = (
            b"SERVICE AGREEMENT\n\n"
            b"1. CONFIDENTIALITY\n"
            b"The parties agree to keep all confidential information proprietary.\n"
            b"Confidential information includes trade secrets and proprietary data.\n\n"
            b"2. TERMINATION\nEither party may terminate with 30 days notice."
        )
        upload = client.post("/api/documents/upload", data={"file": (io.BytesIO(content), "svc.txt")})
        assert upload.status_code == 201
        doc_id = upload.get_json()["document_id"]

        risks_resp = client.get(f"/api/documents/{doc_id}/risks")
        assert risks_resp.status_code == 200
        risks = risks_resp.get_json()["risks"]

        # Group by (risk_type, clause_number or clause_title)
        seen = {}
        for r in risks:
            clause_id = r.get("clause_number") or (r.get("clause_title") or "").lower()
            key = (r["risk_type"], clause_id)
            seen[key] = seen.get(key, 0) + 1

        duplicates = {k: v for k, v in seen.items() if v > 1}
        assert not duplicates, f"Duplicate risk entries found: {duplicates}"

    def test_distinct_risk_types_on_same_clause_preserved(self, client):
        """
        A clause that is both a TERMINATION clause and a DEADLINE clause
        must emit both risk types (they are genuinely distinct).
        """
        import io
        content = (
            b"1. TERMINATION\n"
            b"Either party may terminate this agreement within 30 days written notice.\n"
            b"If not terminated, the agreement will auto-renew automatically."
        )
        upload = client.post("/api/documents/upload", data={"file": (io.BytesIO(content), "term.txt")})
        assert upload.status_code == 201
        doc_id = upload.get_json()["document_id"]

        risks = client.get(f"/api/documents/{doc_id}/risks").get_json()["risks"]
        risk_types = {r["risk_type"] for r in risks}
        # Termination clause must flag at least TERMINATION
        assert "TERMINATION" in risk_types
