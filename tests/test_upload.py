import pytest
import io
import os
from backend.app import app
from backend.database import init_db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'test_uploads')

    with app.app_context():
        init_db()

    with app.test_client() as client:
        yield client

def test_upload_missing_file(client):
    response = client.post('/api/documents/upload')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'No file part'

def test_upload_empty_file(client):
    data = {'file': (io.BytesIO(b""), "empty.txt")}
    response = client.post('/api/documents/upload', data=data)
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Empty file'

def test_upload_invalid_extension(client):
    data = {'file': (io.BytesIO(b"import os"), "script.py")}
    response = client.post('/api/documents/upload', data=data)
    assert response.status_code == 400

def test_upload_txt(client):
    data = {'file': (io.BytesIO(b"1. TERMINATION\nThis contract is terminated."), "test.txt")}
    response = client.post('/api/documents/upload', data=data)
    assert response.status_code == 201
    assert response.get_json()['filename'] == 'test.txt'

def test_search_endpoint(client):
    data = {'file': (io.BytesIO(b"1. TERMINATION\nThis contract is terminated. We like apples."), "test2.txt")}
    upload_res = client.post('/api/documents/upload', data=data).get_json()
    doc_id = upload_res['document_id']

    search_res = client.post(f'/api/documents/{doc_id}/search', json={"query": "apples"})
    assert search_res.status_code == 200
    results = search_res.get_json()['results']
    assert len(results) > 0
    assert "apples" in results[0]['content']
