"""
config.py
Environment-driven settings for the HemoSense FastAPI server.

All secrets (OpenRouter key) come from the environment or api/.env; they are
never hard-coded and never logged.
"""

import os
import sys

API_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(API_DIR)          # the repo root
SCRATCH_DIR = os.path.join(PROJECT_ROOT, "scratch")

for _p in (PROJECT_ROOT, SCRATCH_DIR):  # hemosense/ shared core + legacy scratch modules
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Optional .env in the api/ folder
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(API_DIR, ".env"))
except ImportError:
    pass

# ---- Paths ----
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "models", "anfis.json")


def _resolve(env_name, default):
    """Absolute-path resolution for a setting.

    Relative env values (e.g. "../scratch/...") are interpreted relative to the
    api/ folder, which is where api/.env physically lives.
    """
    value = os.environ.get(env_name, default)
    if not os.path.isabs(value):
        value = os.path.abspath(os.path.join(API_DIR, value))
    return value


MODEL_PATH = _resolve("HEMOSENSE_MODEL_PATH", DEFAULT_MODEL_PATH)

# ---- Upload limits ----
try:
    MAX_UPLOAD_MB = float(os.environ.get("HEMOSENSE_MAX_UPLOAD_MB", "10.0"))
except ValueError:
    MAX_UPLOAD_MB = 10.0
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}

# ---- Amazon Bedrock (primary LLMs, tried in order before OpenRouter) ----
# Auth uses the normal AWS credential chain (EC2 instance role in production).
# Model IDs are Bedrock Converse IDs; set HEMOSENSE_BEDROCK_MODELS to "" to disable Bedrock.
DEFAULT_BEDROCK_MODELS = "deepseek.v3-v1:0,qwen.qwen3-235b-a22b-2507-v1:0,apac.amazon.nova-pro-v1:0"
BEDROCK_MODELS = [m.strip() for m in
                  os.environ.get("HEMOSENSE_BEDROCK_MODELS", DEFAULT_BEDROCK_MODELS).split(",")
                  if m.strip()]
BEDROCK_REGION = os.environ.get("HEMOSENSE_BEDROCK_REGION", "ap-south-1").strip()

# ---- RAG over anaemia guidelines (built by: python -m hemosense.rag build ...) ----
# A missing index file simply disables RAG.
RAG_INDEX_PATH = _resolve("HEMOSENSE_RAG_INDEX", os.path.join(PROJECT_ROOT, "models", "rag_index.json"))
try:
    RAG_TOP_K = int(os.environ.get("HEMOSENSE_RAG_TOP_K", "5"))
except ValueError:
    RAG_TOP_K = 5

# ---- OpenRouter / Dietary Intelligence (fallback chain) ----
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

DEFAULT_LLM_MODELS = (
    "openrouter/free,"
    "google/gemma-4-31b-it:free,"
    "nvidia/nemotron-3-ultra-550b-a55b:free,"
    "google/gemma-4-26b-a4b-it:free,"
    "nvidia/nemotron-3.5-super-vl:free"
)
LLM_MODELS = [m.strip() for m in
              os.environ.get("HEMOSENSE_LLM_MODELS", DEFAULT_LLM_MODELS).split(",")
              if m.strip()]

try:
    LLM_MAX_TOKENS = int(os.environ.get("HEMOSENSE_LLM_MAX_TOKENS", "600"))
except ValueError:
    LLM_MAX_TOKENS = 600

try:
    LLM_TIMEOUT_SECONDS = float(os.environ.get("HEMOSENSE_LLM_TIMEOUT_SECONDS", "60"))
except ValueError:
    LLM_TIMEOUT_SECONDS = 60.0

# ---- CORS ----
CORS_ORIGINS = [o.strip() for o in os.environ.get("HEMOSENSE_CORS_ORIGINS", "*").split(",")
                if o.strip()]