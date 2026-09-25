import os
from backend.utils import safe_log

# Environment variable names
API_KEY_ENV = "GEMINI_API_KEY"
LEGACY_API_KEY_ENV = "LLM_API_KEY"
MODEL_ENV = "GEMINI_MODEL"

DEFAULT_MODEL = "gemini-2.5-flash"

def get_api_key() -> str:
    return os.getenv(API_KEY_ENV) or os.getenv(LEGACY_API_KEY_ENV) or ""

def get_model_name() -> str:
    return os.getenv(MODEL_ENV, DEFAULT_MODEL)

def generate_text(system_prompt: str, user_prompt: str, timeout: int = 30) -> str:
    """Generate a response from Google Gemini LLM provider using official google-genai SDK.

    Reads API key (GEMINI_API_KEY / LLM_API_KEY) and Model name (GEMINI_MODEL) from environment.
    Errors (missing key, network issues, provider errors) are caught safely without logging secrets.
    """
    api_key = get_api_key()
    if not api_key:
        safe_log("error", "LLM API key not configured in environment")
        return "[LLM error: missing API key]"

    model_name = get_model_name()

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            max_output_tokens=500,
            temperature=0.0
        )

        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=config
        )

        if not response or not hasattr(response, "text") or response.text is None:
            safe_log("error", "Gemini API returned an empty or malformed response")
            return "[LLM error: malformed response]"

        return response.text

    except TimeoutError as e:
        safe_log("error", f"Gemini API timeout error: {type(e).__name__}")
        return "[LLM error: connection failed]"
    except Exception as e:
        err_msg = str(e).lower()
        if "timeout" in err_msg or "deadline" in err_msg:
            safe_log("error", f"Gemini API timeout: {type(e).__name__}")
            return "[LLM error: connection failed]"
        safe_log("error", f"Gemini provider error: {type(e).__name__}")
        return "[LLM error: provider returned an error]"
