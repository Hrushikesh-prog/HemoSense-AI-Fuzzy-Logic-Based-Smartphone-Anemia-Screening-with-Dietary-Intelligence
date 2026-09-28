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

if SCRATCH_DIR not in sys.path:
    sys.path.insert(0, SCRATCH_DIR)

# Optional .env in the api/ folder
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(API_DIR, ".env"))
except ImportError:
    pass

# ---- Paths ----
DEFAULT_MODEL_PATH = os.path.join(
    SCRATCH_DIR, "saved_models", "baseline_B_regression_1789914685_final.keras"
)
DEFAULT_META_PATH = os.path.join(
    SCRATCH_DIR, "results", "baseline_B_regression_1789914685_meta.json"
)


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

# Results JSON that carries the chosen run's metrics for /health
META_PATH = _resolve("HEMOSENSE_META_PATH", DEFAULT_META_PATH)

# ---- Upload limits ----
try:
    MAX_UPLOAD_MB = float(os.environ.get("HEMOSENSE_MAX_UPLOAD_MB", "10.0"))
except ValueError:
    MAX_UPLOAD_MB = 10.0
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}

# ---- OpenRouter / Dietary Intelligence ----
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

DEFAULT_LLM_MODELS = (
    "openrouter/free,"
    "deepseek/deepseek-r1:free,"
    "meta-llama/llama-3.3-70b-instruct:free,"
    "google/gemma-3-27b-it:free,"
    "openai/gpt-oss-20b:free,"
    "nvidia/llama-3.1-nemotron-ultra-253b:free"
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