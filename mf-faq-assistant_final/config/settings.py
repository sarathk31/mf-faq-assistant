"""Central settings. Secrets come from environment variables only."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SOURCES_CSV = DATA_DIR / "sources.csv"
RAW_CAPTURES = DATA_DIR / "raw" / "captures.json"
CHUNKS_PATH = DATA_DIR / "processed" / "chunks.json"

# Groq exposes an OpenAI-compatible chat endpoint.
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "8"))


def groq_api_key() -> str | None:
    """Read the key at call time so a missing key never crashes import."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    return key or None


# Retrieval
MIN_RETRIEVAL_SCORE = 1.0   # BM25 score below which evidence is treated as missing
TOP_K = 3

# Input limits
MAX_QUESTION_CHARS = 500

AMC_NAME = "HDFC Mutual Fund"
