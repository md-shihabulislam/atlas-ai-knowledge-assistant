
import os
from pathlib import Path
from dotenv import load_dotenv

# Root project directory
BASE = Path(__file__).resolve().parents[2]

# Load environment variables
load_dotenv(BASE / ".env")

# Google Gemini configuration
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

CHAT_MODEL = os.getenv(
    "GEMINI_CHAT_MODEL",
    "gemini-3.5-flash-lite"
)

EMBEDDING_MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL",
    "gemini-embedding-2"
)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

SQLITE_PATH = os.getenv(
    "SQLITE_PATH",
    str(BASE / "knowledge.db")
)

# Frontend access
CORS_ORIGINS = [
    s.strip()
    for s in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173"
    ).split(",")
    if s.strip()
]

# Upload restrictions
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 50
MAX_CHUNKS = 200
