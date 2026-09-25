import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///legalease.db")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    LLM_API_KEY = GEMINI_API_KEY
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
