"""
Configuration via environment variables. No hardcoded paths or secrets.
"""
import os

# Load .env if present (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Monday.com API - required for dynamic data fetch
MONDAY_API_TOKEN = os.environ.get("MONDAY_API_TOKEN", "")
MONDAY_API_URL = "https://api.monday.com/v2"

# Board IDs - set after creating boards and importing CSVs (get from Monday.com board URL or API)
WORK_ORDERS_BOARD_ID = os.environ.get("MONDAY_WORK_ORDERS_BOARD_ID", "")
DEALS_BOARD_ID = os.environ.get("MONDAY_DEALS_BOARD_ID", "")

# LLM - open source / free tier options
# Option 1: Groq (free tier, no key for local testing with fallback)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Option 2: Ollama (local, open source)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# Which provider to use: "groq" | "ollama"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")

# Cache TTL in seconds for Monday.com data (reduce API calls, still dynamic)
DATA_CACHE_TTL_SECONDS = int(os.environ.get("DATA_CACHE_TTL_SECONDS", "300"))
