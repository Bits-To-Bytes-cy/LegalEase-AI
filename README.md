# LegalEase AI

## Challenge Vertical
AI for Legal Assistance & Access

## Problem
Legal documents—such as employment agreements, lease contracts, non-disclosure agreements, and terms of service—are filled with complex legalese, hidden obligations, tight deadlines, and severe liability clauses. Most non-lawyers struggle to read and interpret these documents, leading to signed agreements with unexpected financial or legal consequences. However, professional legal consultation is expensive, inaccessible, and often slow for routine document understanding.

## Solution
LegalEase AI is an intelligent, evidence-grounded legal assistance platform that simplifies complex legal contracts for everyday individuals and small business owners. It provides automated summaries, risk analysis, deadline extractions, clause explanations, two-document comparisons, practical next-step guidance, and lawyer preparation briefs. LegalEase AI operates under a strict "evidence-first" rule, ensuring all responses are directly linked to specific text chunks within the uploaded document while adhering strictly to zero-dependency constraints and repository size limits (<10 MB).

## Key Features
* **Multi-Format Document Upload**: Support for PDF, DOCX, and TXT files with local processing.
* **Plain-Language Summarization**: Structured summaries including document type, parties, duration, and key obligations.
* **Document Q&A with Evidence**: Interactive chat grounded in retrieved document chunks with clear page and clause citations.
* **Risk & Review-Worthy Clause Detection**: Deterministic and heuristic risk engine flagging review-worthy provisions with explicit severity tags (`INFO`, `REVIEW`, `IMPORTANT`).
* **Time-Bound Provision & Deadline Detection**: Automatic extraction of dates, notice periods, and renewal deadlines.
* **Internal Consistency & Contradiction Checking**: Automated detection of conflicting definitions or conflicting termination periods within the same agreement.
* **Clause-Level Deep Explanations**: Side-by-side view comparing original legal text to plain-language breakdown and practical impact.
* **Two-Document Comparison**: Deterministic comparison engine classifying changes as `UNCHANGED`, `MODIFIED`, `ADDED`, or `REMOVED` with text diffs.
* **Practical Next-Step Guidance**: Actionable considerations, verification checklists, and jurisdiction-aware context.
* **Lawyer Consultation Brief**: Generates a structured 8-section case preparation brief to maximize efficiency during legal consultations.
* **Jurisdiction Awareness**: Optional country and region input to tailor contextual guidance (e.g., state/country specific notices).
* **Robust Prompt-Injection & Safety Defenses**: Defense-in-depth security preventing untrusted document content from hijacking assistant behavior.

## Smart Assistant Logic
LegalEase AI employs a deterministic-first, evidence-linked pipeline:
1. **User Request & Context**: User submits a query or requests an analysis (along optional jurisdiction details).
2. **Intent Detection**: Lightweight, rule-augmented intent router classifies the request (`SUMMARY`, `QUESTION`, `EXPLAIN_CLAUSE`, `RISK_ANALYSIS`, `COMPARE`, `NEXT_STEPS`, `LAWYER_PREPARATION`).
3. **Document / Evidence Retrieval**: Top relevant text chunks are retrieved from the local database using local keyword and similarity matching.
4. **Appropriate Feature Execution**: Deterministic engines perform initial structural analysis, diffing, or risk checking before invoking AI.
5. **AI Generation (When Needed)**: System prompt enforces safety guidelines, treating document context strictly as untrusted evidence.
6. **Output Validation**: Multi-layer post-processing validates AI output for secret leakage, system prompt exposure, or invalid legal guarantees.
7. **Evidence-Linked Response**: Response is rendered with source chips pointing directly to page and clause numbers.

## Architecture
LegalEase AI is built as a lightweight, zero-heavy-dependency web application:
* **Flask (Python Backend)**: Serves API endpoints, manages application lifecycle, handles file processing, and serves static assets.
* **SQLite Database**: Lightweight local storage for document records, chunks, chat history, and risk flags with enabled cascading foreign keys.
* **Document Processor (`document_processor.py`)**: Extracts text from PDF (pypdf), DOCX (python-docx), and TXT files, chunking content along clause boundaries.
* **Retrieval Engine (`retrieval.py`)**: Performs keyword and phrase matching across indexed document chunks.
* **AI Engine Abstraction (`ai_engine.py`)**: Provider-agnostic wrapper interfacing with LLM APIs via standard HTTP requests without heavy SDKs.
* **Safety Layer (`safety.py`)**: Centralized prompt injection detection, context sanitization, and output validation.
* **Analysis Modules**: Dedicated modules for summary (`summary.py`), risks (`risk_engine.py`), deadlines (`deadline_detection.py`), consistency (`consistency.py`), clause explanation (`clause_explanation.py`), comparison (`comparison.py`), next steps (`next_steps.py`), and lawyer prep (`lawyer_prep.py`).
* **Frontend (`templates/index.html`, `static/style.css`, `static/app.js`)**: Single-Page Application (SPA) built with semantic HTML5, modern vanilla CSS, and standard ES6 JavaScript.

## Retrieval / RAG
Instead of passing entire long legal documents to the LLM—which increases latency, cost, and risk of hallucinations—LegalEase AI indexes document chunks into SQLite upon upload. When a user asks a question, the retrieval engine scores and extracts only the top relevant chunks (`top_k=5`). These chunks are sanitized with evidence headers and injected into the prompt as bounded context. If no relevant chunks are found, the system refrains from inventing information.

## Security
* **Secure Filenames & Paths**: Uploaded files use `secure_filename` and explicit path traversal checks (`os.path.abspath`) to guarantee files stay inside the designated upload directory.
* **Upload Validation**: Strict extension (`.pdf`, `.docx`, `.txt`), MIME type, and maximum file size (16 MB) validation with clean JSON error handling.
* **Secret Protection**: Zero hardcoded API keys in source code, HTML, or JavaScript. Environment credentials are read strictly from `.env` (ignored by git).
* **Prompt Injection Defense**: Defense-in-depth mechanism detecting prompt overrides (e.g., "IGNORE ALL PREVIOUS INSTRUCTIONS") and treating all document text strictly as passive evidence.
* **Output Validation**: Post-execution checks scan LLM output to prevent leakage of secrets, system prompts, or promises of guaranteed legal outcomes.
* **Safe Logging**: `safe_log` prevents logging sensitive document content, user legal queries, or environment credentials to stdout/files.
* **Cascading Document Deletion**: `DELETE /api/documents/<id>` removes physical files from disk and relies on SQLite foreign key constraints to purge database records safely.

## Accessibility
* **Semantic HTML5**: Uses proper landmark elements (`<header>`, `<main>`, `<section>`, `<nav>`, `<footer>`) and heading hierarchies (`<h1>`-`<h4>`).
* **Keyboard Navigation & Visible Focus**: Global `:focus-visible` styling provides high-contrast focus rings across all inputs, buttons, tabs, and interactive clause cards.
* **ARIA Attributes**: Uses `aria-label`, `aria-selected`, `aria-controls`, `aria-live`, and `role` attributes for tab panels, loader screens, and popups.
* **Non-Color-Only Indicators**: Risk severity level is always explicitly textually labeled (`INFO`, `REVIEW`, `IMPORTANT`), ensuring clarity for color-blind users.
* **Screen-Reader States**: Dynamic content updates use `aria-live="polite"` and visual hidden states are synchronized with `hidden` attributes.

## Efficiency
* **Minimal Repository Footprint**: Under 10 MB total repository size without large ML binaries, vector database binaries, or bulky UI frameworks.
* **Single Extraction Ingestion**: Text extraction and chunking occur once during upload.
* **Deterministic Analysis First**: Comparison, clause matching, deadline extraction, and risk checking use regex and deterministic diffing prior to optional LLM calls.
* **Targeted LLM Payloads**: LLMs receive bounded evidence snippets rather than full document texts, minimizing token consumption.

## Testing
* **Pytest Suite**: Complete test coverage in `tests/` covering API endpoints, document parsing, retrieval, risk detection, comparison, guidance, lawyer prep, prompt injection defense, secret leakage, and document deletion.
* **Zero API Key Requirement for Testing**: All AI provider calls are fully mocked in unit and integration tests, allowing `pytest` to run offline anywhere.
* **Submission Checker**: `tools/check_submission.py` validates repository size, forbidden files, environment settings, and code hygiene.

## Assumptions
* Documents uploaded are text-based PDFs, DOCX, or plain text files.
* Users seek legal information and orientation rather than formal legal representation.
* Standard jurisdiction context (country/region) provides general orientation rules rather than real-time statutory database lookups.

## Limitations
* **No OCR Support**: Scanned or image-only PDFs without an embedded text layer cannot be parsed without external OCR tools.
* **Lightweight Keyword Retrieval**: Search relies on deterministic keyword and phrase matching rather than dense vector embeddings to adhere to zero-dependency and <10 MB constraints.
* **Jurisdiction Differences**: Statutory provisions vary widely; automated guidance is informational and cannot replace local legal counsel.
* **Heuristic Defenses**: Regex-based prompt injection detection flags common injection patterns but cannot guarantee prevention of all theoretical adversarial attacks.
* **Risk Flags as Review Prompts**: Risk engine flags provisions for review; flags do not constitute definitive legal invalidity or illegality.

## Installation
```bash
# Clone repository
git clone <repository_url>
cd <repository_name>

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Contents of `.env.example`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
DATABASE_URI=sqlite:///legalease.db
DEBUG=False
```

## Storage Limitation Disclaimer
> [!IMPORTANT]
> On the default Render filesystem, uploaded documents and local SQLite data are ephemeral and may be lost when the service restarts or redeploys. The prototype is intended for demonstration. Production deployment would use persistent storage/database.

## Deploying to Render

Follow these steps to deploy LegalEase AI on Render:

1. **Push Repository**: Push your public repository to GitHub.
2. **Create Web Service**: Log in to [Render](https://render.com), click **New +**, and select **Web Service**.
3. **Connect Repository**: Select and connect your LegalEase AI GitHub repository.
4. **Configure Build & Start Commands**:
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -b 0.0.0.0:$PORT backend.app:app`
5. **Set Environment Variables**: In the Render Dashboard under **Environment**:
   - `GEMINI_API_KEY`: Set to your Google Gemini API key (do not commit this key to Git).
   - `GEMINI_MODEL`: Set to `gemini-3.6-flash` (or preferred Gemini model).
   - `DATABASE_URI`: Set to `sqlite:///legalease.db`.
6. **Health Check Path**: Set health check path to `/api/health`.
7. **Deploy**: Click **Create Web Service**. Once deployed, open the Render service URL.
8. **Verify**: Test `/api/health` and perform document analysis workflows on the web interface.

## Running
Start the Flask application server locally:
```bash
python -m backend.app
```
Or start using Gunicorn (production mode):
```bash
gunicorn -b 0.0.0.0:5000 backend.app:app
```
The application will be accessible in your web browser at `http://127.0.0.1:5000`.

## Testing
Execute the complete automated test suite:
```bash
pytest -q
```
Execute submission compliance check:
```bash
python tools/check_submission.py
```

## Submission Compliance
* **Public GitHub Repository**: Single clean branch repository structure.
* **Repository Size**: Strictly under 10 MB total size.
* **Zero Secrets**: No API keys, passwords, or secret credentials committed.
* **Complete Source Code**: Fully functional backend, frontend, tools, and test suite included.
* **Comprehensive Documentation**: Complete `README.md` provided.

## Legal Information Disclaimer
LegalEase AI provides legal information and document assistance. It is not a lawyer, does not provide legal representation or definitive legal advice, and does not guarantee legal outcomes. Users should always consult a qualified legal professional for consequential legal matters.
