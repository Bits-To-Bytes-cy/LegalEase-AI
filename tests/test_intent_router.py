import pytest
from backend.intent_router import detect_intent

@pytest.fixture(autouse=True)
def mock_intent_llm(monkeypatch):
    def fake_generate(system_prompt, user_prompt):
        lowered = user_prompt.lower()
        if "terminate early" in lowered:
            return "QUESTION"
        if "india" in lowered:
            return "GENERAL_INFORMATION"
        return "GENERAL_INFORMATION"
    monkeypatch.setattr('backend.intent_router.generate_text', fake_generate)
    monkeypatch.setattr('backend.ai_engine.generate_text', fake_generate)

@pytest.mark.parametrize('message,expected_intent', [
    ("What is this agreement about?", "SUMMARY"),
    ("What happens if I terminate early?", "QUESTION"),
    ("Tell me about the law in India.", "GENERAL_INFORMATION"),
])
def test_detect_intent_deterministic(message, expected_intent):
    result = detect_intent(message)
    assert result["intent"] == expected_intent
    assert isinstance(result["reason"], str)
