import math
from collections import Counter
import string
from backend.database import get_db_connection

def tokenize(text):
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text.split()

def compute_tf(tokens):
    tf = Counter(tokens)
    total_tokens = len(tokens)
    if total_tokens == 0:
        return tf
    for word in tf:
        tf[word] = tf[word] / total_tokens
    return tf

def compute_idf(documents):
    idf = {}
    N = len(documents)
    if N == 0:
        return idf
    for doc in documents:
        unique_words = set(doc)
        for word in unique_words:
            idf[word] = idf.get(word, 0) + 1
    for word, num_docs in idf.items():
        # Add smoothing + 1 so idf is never 0
        idf[word] = math.log10((N + 1) / (float(num_docs) + 1)) + 1.0
    return idf

def retrieve_relevant_chunks(document_id, query, top_k=5):
    conn = get_db_connection()
    chunks = conn.execute('SELECT id, clause_title, content, page_number, clause_number FROM chunks WHERE document_id = ?', (document_id,)).fetchall()
    conn.close()

    if not chunks:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    chunk_tokens = []
    for chunk in chunks:
        text = (chunk['clause_title'] or '') + " " + chunk['content']
        chunk_tokens.append(tokenize(text))

    idf = compute_idf(chunk_tokens)

    scores = []
    for i, c_tokens in enumerate(chunk_tokens):
        tf = compute_tf(c_tokens)
        score = 0
        for q_word in query_tokens:
            if q_word in tf and q_word in idf:
                score += tf[q_word] * idf[q_word]
        scores.append((score, chunks[i]))

    scores.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, chunk in scores[:top_k]:
        if score > 0:
            results.append({
                "id": chunk['id'],
                "clause_title": chunk['clause_title'],
                "clause_number": chunk['clause_number'],
                "content": chunk['content'],
                "page_number": chunk['page_number'],
                "score": score
            })

    return results
