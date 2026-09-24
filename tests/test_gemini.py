import os
import pytest
import io
import json
from backend.ai_engine import generate_text
from backend.app import app

def test_missing_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    res = generate_text("System", "User")
    assert res == "[LLM error: missing API key]"

def test_successful_mocked_gemini_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key_12345")

    class DummyResponse:
        text = "This is a mocked Gemini response."

    class DummyModels:
        def generate_content(self, model, contents, config=None):
            return DummyResponse()

    class DummyClient:
        def __init__(self, api_key=None):
            self.models = DummyModels()

    import google.genai
    monkeypatch.setattr(google.genai, "Client", DummyClient)

    res = generate_text("System", "User")
    assert res == "This is a mocked Gemini response."

def test_gemini_api_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key_12345")

    class DummyModelsError:
        def generate_content(self, model, contents, config=None):
            raise Exception("403 Invalid API key")

    class DummyClientError:
        def __init__(self, api_key=None):
            self.models = DummyModelsError()

    import google.genai
    monkeypatch.setattr(google.genai, "Client", DummyClientError)

    res = generate_text("System", "User")
    assert res == "[LLM error: provider returned an error]"
    assert "mock_key_12345" not in res

def test_gemini_timeout_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key_12345")

    class DummyModelsTimeout:
        def generate_content(self, model, contents, config=None):
            raise TimeoutError("Deadline exceeded")

    class DummyClientTimeout:
        def __init__(self, api_key=None):
            self.models = DummyModelsTimeout()

    import google.genai
    monkeypatch.setattr(google.genai, "Client", DummyClientTimeout)

    res = generate_text("System", "User")
    assert res == "[LLM error: connection failed]"

def test_malformed_gemini_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key_12345")

    class DummyResponseMalformed:
        text = None

    class DummyModelsMalformed:
        def generate_content(self, model, contents, config=None):
            return DummyResponseMalformed()

    class DummyClientMalformed:
        def __init__(self, api_key=None):
            self.models = DummyModelsMalformed()

    import google.genai
    monkeypatch.setattr(google.genai, "Client", DummyClientMalformed)

    res = generate_text("System", "User")
    assert res == "[LLM error: malformed response]"

def test_frontend_does_not_contain_api_key():
    with open("static/app.js", "r", encoding="utf-8") as f:
        js_content = f.read()
    assert "GEMINI_API_KEY" not in js_content
    assert "AIza" not in js_content
    assert "google.genai" not in js_content
    assert "https://generativelanguage.googleapis.com" not in js_content

def test_workflows_with_gemini_mock(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key_12345")

    class DummyResponse:
        text = "Mocked Gemini text output"

    class DummyModels:
        def generate_content(self, model, contents, config=None):
            return DummyResponse()

    class DummyClient:
        def __init__(self, api_key=None):
            self.models = DummyModels()

    import google.genai
    monkeypatch.setattr(google.genai, "Client", DummyClient)

    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = '.tmp_uploads'
    with app.test_client() as client:
        # Upload doc
        data = {'file': (io.BytesIO(b"1. Clause One: Tenant agrees to pay rent."), 'gemini_test.txt')}
        rv = client.post('/api/documents/upload', data=data, content_type='multipart/form-data')
        doc_id = json.loads(rv.data)['document_id']

        # Chat
        res = client.post(f'/api/documents/{doc_id}/chat', json={"question": "What does clause one say?"})
        assert res.status_code == 200
        assert "evidence" in json.loads(res.data)

        # Summary
        res_sum = client.post(f'/api/documents/{doc_id}/summary')
        assert res_sum.status_code == 200

        # Next steps
        res_ns = client.post(f'/api/documents/{doc_id}/next-steps')
        assert res_ns.status_code == 200

        # Lawyer prep
        res_lp = client.post(f'/api/documents/{doc_id}/lawyer-prep')
        assert res_lp.status_code == 200
