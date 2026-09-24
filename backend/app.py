from flask import Flask, jsonify, request, render_template
from backend.database import init_db, get_db_connection
from backend.utils import safe_log
from backend.ai_engine import generate_text
from backend.config import Config
from backend.document_processor import process_document
from backend.retrieval import retrieve_relevant_chunks
from backend.safety import detect_prompt_injection, sanitize_retrieved_context, validate_ai_output
from backend.intent_router import detect_intent
from backend.prompts import SYSTEM_PROMPT, QUESTION_PROMPT
from backend.risk_engine import analyze_risks
from backend.deadline_detection import detect_deadlines
from backend.consistency import check_consistency
from backend.summary import generate_summary, get_important_clauses
from backend.clause_explanation import explain_clause
from backend.comparison import compare_documents
from backend.next_steps import generate_next_steps
from backend.lawyer_prep import generate_lawyer_prep
from werkzeug.utils import secure_filename
import os

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))

app.config.from_object(Config)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB max upload sizes (we want to keep it small)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
ALLOWED_MIMES = {'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'}

def allowed_file(filename, mimetype):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS and mimetype in ALLOWED_MIMES

@app.errorhandler(404)
def not_found_error(error):
    safe_log("error", "404 Error: Resource not found")
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    safe_log("error", "500 Error: Internal server error")
    return jsonify({"error": "Internal server error"}), 500

from werkzeug.exceptions import RequestEntityTooLarge

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    safe_log("error", "413 Error: File too large")
    return jsonify({"error": "File exceeds maximum allowed size (16 MB)"}), 413

@app.errorhandler(Exception)
def handle_exception(e):
    safe_log("error", f"Unhandled Exception: {type(e).__name__}")
    return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "LegalEase AI"}), 200

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    if size == 0:
        return jsonify({"error": "Empty file"}), 400
    file.seek(0)

    if file and allowed_file(file.filename, file.mimetype):
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Path traversal protection
        if not os.path.abspath(filepath).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return jsonify({"error": "Invalid file path"}), 400

        file.save(filepath)

        # Determine jurisdiction
        country = request.form.get("country", "")
        region = request.form.get("region", "")

        # database insertion
        conn = get_db_connection()
        cursor = conn.cursor()
        ext = filename.rsplit('.', 1)[1].lower()
        cursor.execute('''
            INSERT INTO documents (filename, file_type, status, jurisdiction_country, jurisdiction_region)
            VALUES (?, ?, ?, ?, ?)
        ''', (filename, ext, 'processing', country, region))
        conn.commit()
        doc_id = cursor.lastrowid

        # Parse it properly
        result = process_document(filepath, file.filename)
        if result['status'] == 'success':
            cursor.execute('UPDATE documents SET status = ? WHERE id = ?', ('completed', doc_id))
            for chunk in result['chunks']:
                cursor.execute('''
                    INSERT INTO chunks (document_id, page_number, clause_number, clause_title, content)
                    VALUES (?, ?, ?, ?, ?)
                ''', (doc_id, chunk['page_number'], chunk['clause_number'], chunk['clause_title'], chunk['content']))
            conn.commit()
            conn.close()
            return jsonify({
                "document_id": doc_id,
                "filename": filename,
                "type": ext,
                "status": "completed",
                "page_count": result.get("page_count", 0),
                "character_count": result.get("char_count", 0)
            }), 201
        else:
            cursor.execute('UPDATE documents SET status = ? WHERE id = ?', ('error', doc_id))
            conn.commit()
            conn.close()
            return jsonify({"error": result['error']}), 500
    else:
        return jsonify({"error": "Invalid file type or extension"}), 400

@app.route('/api/documents', methods=['GET'])
def list_documents():
    conn = get_db_connection()
    docs = conn.execute('SELECT id, filename, file_type, status, created_at FROM documents').fetchall()
    conn.close()
    return jsonify([dict(d) for d in docs]), 200

@app.route('/api/documents/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    conn = get_db_connection()
    doc = conn.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()
    if doc is None:
        return jsonify({"error": "Document not found"}), 404
    return jsonify(dict(doc)), 200

@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    conn = get_db_connection()
    doc = conn.execute('SELECT id, filename FROM documents WHERE id = ?', (doc_id,)).fetchone()
    if not doc:
        conn.close()
        return jsonify({"error": "Document not found"}), 404

    # Delete from database (cascades to chunks, messages, risk_flags)
    conn.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
    conn.commit()
    conn.close()

    # Delete file from filesystem
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc['filename'])
    if os.path.exists(filepath):
        os.remove(filepath)

    safe_log("info", f"Deleted document {doc_id} and associated file.")
    return jsonify({"success": True}), 200

@app.route('/api/documents/<int:doc_id>/search', methods=['POST'])
def search_document(doc_id):
    data = request.json or {}
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "Missing query"}), 400

    results = retrieve_relevant_chunks(doc_id, query, top_k=5)
    return jsonify({"results": results}), 200



# Chat endpoint – document specific Q&A
@app.route('/api/documents/<int:doc_id>/chat', methods=['POST'])
def chat_document(doc_id):
    data = request.json or {}
    question = data.get('question', '').strip()
    country = data.get('country', '')
    region = data.get('region', '')
    if not question:
        return jsonify({"error": "Missing question"}), 400

    if detect_prompt_injection(question):
        return jsonify({"error": "Unsafe input detected"}), 400

    # Intent detection
    intent_info = detect_intent(question, document_present=True, jurisdiction_present=bool(country or region))
    intent = intent_info["intent"]
    # Retrieve evidence (only for intents that need document)
    evidence = []
    if intent_info.get('requires_document'):
        chunks = retrieve_relevant_chunks(doc_id, question, top_k=5)
        # Convert to dict list for response
        evidence = [{
            "chunk_id": c["id"],
            "page": c["page_number"],
            "clause": c.get("clause_number"),
            "title": c.get("clause_title"),
            "text": c.get("content")
        } for c in chunks]
        # Sanitize for LLM
        sanitized_context = sanitize_retrieved_context(chunks)
    else:
        sanitized_context = ""
    # Build LLM prompt
    user_prompt = f"Question: {question}\n\nEvidence:\n{sanitized_context}" if sanitized_context else f"Question: {question}"
    # Call LLM
    raw_answer = generate_text(SYSTEM_PROMPT, user_prompt)
    # Validate output
    if not validate_ai_output(raw_answer):
        raw_answer = "[Safety filter removed unsafe content]"
    response = {
        "intent": intent,
        "answer": raw_answer,
        "evidence": evidence,
        "needs_professional_review": True
    }
    return jsonify(response), 200

# Chunk source endpoint
@app.route('/api/chunks/<int:chunk_id>', methods=['GET'])
def get_chunk(chunk_id):
    conn = get_db_connection()
    chunk = conn.execute('SELECT * FROM chunks WHERE id = ?', (chunk_id,)).fetchone()
    conn.close()
    if not chunk:
        return jsonify({"error": "Chunk not found"}), 404
    return jsonify(dict(chunk)), 200


# ───────────────────────────── Prompt 4 routes ─────────────────────────────

@app.route('/api/documents/<int:doc_id>/summary', methods=['POST'])
def document_summary(doc_id):
    result = generate_summary(doc_id)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200


@app.route('/api/documents/<int:doc_id>/explain', methods=['POST'])
def document_explain(doc_id):
    data = request.json or {}
    chunk_id = data.get('chunk_id')
    if not chunk_id:
        return jsonify({'error': 'chunk_id is required'}), 400
    result = explain_clause(int(chunk_id))
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200


@app.route('/api/documents/<int:doc_id>/risks', methods=['GET'])
def document_risks(doc_id):
    # Verify document exists
    conn = get_db_connection()
    doc = conn.execute('SELECT id FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    flags = analyze_risks(doc_id)
    return jsonify({'document_id': doc_id, 'risks': flags}), 200


@app.route('/api/documents/<int:doc_id>/deadlines', methods=['GET'])
def document_deadlines(doc_id):
    conn = get_db_connection()
    doc = conn.execute('SELECT id FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    deadlines = detect_deadlines(doc_id)
    return jsonify({'document_id': doc_id, 'deadlines': deadlines}), 200


@app.route('/api/documents/<int:doc_id>/consistency', methods=['GET'])
def document_consistency(doc_id):
    conn = get_db_connection()
    doc = conn.execute('SELECT id FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    issues = check_consistency(doc_id)
    return jsonify({'document_id': doc_id, 'issues': issues}), 200


@app.route('/api/documents/<int:doc_id>/important-clauses', methods=['GET'])
def document_important_clauses(doc_id):
    conn = get_db_connection()
    doc = conn.execute('SELECT id FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    clauses = get_important_clauses(doc_id)
    return jsonify({'document_id': doc_id, 'important_clauses': clauses}), 200


# ───────────────────────────── Prompt 5 routes ─────────────────────────────

@app.route('/api/documents/compare', methods=['POST'])
def compare_docs():
    data = request.json or {}
    doc_a_id = data.get('document_a_id')
    doc_b_id = data.get('document_b_id')

    if not doc_a_id or not doc_b_id:
        return jsonify({'error': 'Both document_a_id and document_b_id are required'}), 400

    try:
        doc_a_id = int(doc_a_id)
        doc_b_id = int(doc_b_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid document IDs'}), 400

    result = compare_documents(doc_a_id, doc_b_id)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200


@app.route('/api/documents/<int:doc_id>/next-steps', methods=['POST'])
def next_steps_endpoint(doc_id):
    data = request.get_json(silent=True) or {}
    situation = data.get('situation', '')
    country = data.get('country', '')
    region = data.get('region', '')

    result = generate_next_steps(doc_id, situation=situation, country=country, region=region)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200


@app.route('/api/documents/<int:doc_id>/lawyer-prep', methods=['POST'])
def lawyer_prep_endpoint(doc_id):
    data = request.get_json(silent=True) or {}
    situation = data.get('situation', '')
    country = data.get('country', '')
    region = data.get('region', '')

    result = generate_lawyer_prep(doc_id, situation=situation, country=country, region=region)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200



# ─────────────────────────── App startup ───────────────────────────────────

# Initialize DB on startup
with app.app_context():
    init_db()

if __name__ == '__main__':
    safe_log('info', 'Starting Flask application...')
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=port)
