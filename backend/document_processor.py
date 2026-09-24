import os
import re
from pypdf import PdfReader
from docx import Document
from backend.utils import safe_log

# Common clause headers
CLAUSE_PATTERNS = [
    r"^\d+\.\s+[A-Z]", # Numbered clauses like "1. Definitions"
    r"^SECTION\s+\d+",
    r"^ARTICLE\s+\d+",
    r"(?i)\bTERMINATION\b",
    r"(?i)\bLIABILITY\b",
    r"(?i)\bINDEMNITY\b",
    r"(?i)\bPAYMENT\b",
    r"(?i)\bCONFIDENTIALITY\b",
    r"(?i)\bRENEWAL\b",
    r"(?i)\bJURISDICTION\b",
    r"(?i)\bDISPUTE RESOLUTION\b"
]

def format_chunks(text, file_type="txt", page_num=None):
    # simple chunker that respects clause boundaries
    # split by paragraphs first
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current_clause_title = None
    current_clause_number = None

    def detect_clause(para):
        for pattern in CLAUSE_PATTERNS:
            if re.search(pattern, para):
                return True
        return False

    def update_clause_info(para):
        nonlocal current_clause_number, current_clause_title
        match = re.match(r'^(\d+\.)\s+(.*)', para)
        if match:
            current_clause_number = match.group(1).strip()
            current_clause_title = match.group(2).strip()
        else:
            current_clause_title = para[:50]
            current_clause_number = None

    current_text = ""
    for para in paragraphs:
        if detect_clause(para):
            if len(current_text) > 0:
                chunks.append({
                    "page_number": page_num,
                    "clause_title": current_clause_title,
                    "clause_number": current_clause_number,
                    "content": current_text
                })
            current_text = para
            update_clause_info(para)
        else:
            if current_text:
                current_text += "\n" + para
            else:
                current_text = para
                # Maybe it's the start of the doc without a clause header
                current_clause_title = "Document Start"
                current_clause_number = None

    if current_text:
        chunks.append({
            "page_number": page_num,
            "clause_title": current_clause_title,
            "clause_number": current_clause_number,
            "content": current_text
        })

    # further split large chunks > 1000 characters
    final_chunks = []
    for chunk in chunks:
        content = chunk["content"]
        if len(content) > 1500:
            words = content.split()
            sub_chunk = []
            sub_len = 0
            for w in words:
                if sub_len + len(w) > 1000:
                    chunk_copy = chunk.copy()
                    chunk_copy["content"] = " ".join(sub_chunk)
                    final_chunks.append(chunk_copy)
                    # overlap
                    sub_chunk = sub_chunk[-20:] + [w]
                    sub_len = sum(len(x)+1 for x in sub_chunk)
                else:
                    sub_chunk.append(w)
                    sub_len += len(w) + 1
            if sub_chunk:
                chunk_copy = chunk.copy()
                chunk_copy["content"] = " ".join(sub_chunk)
                final_chunks.append(chunk_copy)
        else:
            final_chunks.append(chunk)

    return final_chunks

def process_document(filepath, original_filename):
    ext = filepath.rsplit('.', 1)[1].lower()
    chunks = []
    try:
        if ext == 'pdf':
            reader = PdfReader(filepath)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    page_chunks = format_chunks(text, ext, page_num=i+1)
                    chunks.extend(page_chunks)
        elif ext == 'docx':
            doc = Document(filepath)
            text = "\n".join([p.text for p in doc.paragraphs])
            chunks = format_chunks(text, ext, page_num=1)
        elif ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            chunks = format_chunks(text, ext, page_num=1)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

        char_count = sum(len(c['content']) for c in chunks)
        page_count = 1
        if ext == 'pdf':
            page_count = len(reader.pages)
        return {"status": "success", "chunks": chunks, "page_count": page_count, "char_count": char_count}
    except Exception as e:
        safe_log("error", f"Error processing {original_filename}: {str(e)}")
        return {"status": "error", "error": "Could not process document. The file may be corrupt, password-protected, or unsupported."}
