# HemoSense API — Implementation Plan

A FastAPI backend that turns the trained HemoSense anemia-screening CNN into
callable HTTP endpoints, plus an LLM-backed "Dietary Intelligence" layer that
uses the screening result to give personalized dietary recommendations.

The API does **not** re-implement any of the Phase 2/3 pipeline. It imports the
existing modules in `../scratch` and reuses them unchanged:

- `anemia_pipeline.py` — `extract_conjunctiva_roi()`, `apply_fuzzy_correction()`, `calculate_erythema_index()`
- `evaluate.py` — `hb_to_severity()` (bins match the training labels exactly)
- `config.py` / `data_loader.py` — preprocessing contract (resize 224x224, `/255.0`)
- Best trained model: `scratch/saved_models/baseline_B_regression_1789914685_final.keras`
  (variant B = fuzzy-corrected, MAE 1.404 g/dL, binary screening acc 0.815, sens 0.778, spec 0.839)

---

## 1. Repository layout

```
api/
  API_PLAN.md        # this document
  README.md          # quickstart
  requirements.txt   # API-only deps (FastAPI side)
  .env.example       # env template (OpenRouter key, model list, ...)
  main.py            # FastAPI app; lifespan loads the CNN and warms it up
  config.py          # env-driven settings + path resolution to ../scratch
  schemas.py         # Pydantic request/response models
  pipeline.py        # image -> ROI -> fuzzy-correct -> CNN predict
  llm.py             # OpenRouter client with multi-model fallback chain
```

All Python modules under `api/` add `../scratch` to `sys.path` so the Phase 2/3
modules import directly from that folder.

---

## 2. Dependencies

`api/requirements.txt` (the web/API layer only):

```
fastapi
uvicorn[standard]
python-multipart
python-dotenv
openai
```

The heavy ML stack is already pinned in `scratch/requirements.txt`
(`tensorflow<2.17`, `opencv-python>=4.8`, `scikit-fuzzy>=0.4.2`, `numpy>=1.24,<2.0`).

> **Runtime note (important).** `tensorflow<2.17` requires Python 3.11/3.12.
> The API must run in the same environment used to train the models
> (e.g. the project's conda env `Capstoneprojectenvironment`).
> On machines without that env, the app still boots and all endpoints except
> `POST /screen` and `POST /screen/roi` work; those return a clear `503`
> explaining that the CNN is unavailable.

---

## 3. Endpoints

### 3.1 `GET /health`
Liveness + model status.

```json
{
  "status": "ok",
  "model": {
    "name": "baseline_B_regression_1789914685",
    "variant": "B",
    "head": "regression",
    "loaded": true,
    "path": "C:/.../saved_models/baseline_B_regression_1789914685_final.keras"
  },
  "metrics": {
    "overall_mae": 1.404,
    "overall_rmse": 1.869,
    "severity_4class_accuracy": 0.707,
    "binary_screening": { "accuracy": 0.815, "sensitivity": 0.778, "specificity": 0.839 },
    "per_region": { "India": {...}, "Italy": {...} }
  }
}
```

Metrics are read from the saved `results/baseline_B_regression_1789914685_meta.json`
/ `_test_metrics.json` (no recomputation at runtime).

### 3.2 `POST /screen`
Upload a photo of the eye/face (`multipart/form-data`, field `image`).

Pipeline, exactly as in training:
1. `extract_conjunctiva_roi(image)` — Haar-cascade face → eye → lower-eyelid crop
   (existing fallbacks when no face/eye is found).
2. `apply_fuzzy_correction(roi)` — skfuzzy lighting normalization.
3. Preprocess: decode → resize to **224x224** → `float32 / 255.0` (matches
   `data_loader._decode_and_resize`). The model's own first layer applies
   `Rescaling(255.0)` + EfficientNet `preprocess_input`.
4. CNN regression → predicted hemoglobin in g/dL.
5. Severity via `evaluate.hb_to_severity` (`np.digitize(... , right=True)`), so
   bins line up with the `severity_class` column from training.
6. Anemia flag: `Hb <= 12.0` (WHO-consistent, matches the saved binary metrics).

Response:

```json
{
  "predicted_hb_gdl": 11.3,
  "severity_class": "Mild",
  "anemic": true,
  "erythema_index": { "raw": 0.183, "corrected": 0.171 },
  "roi": { "detected": true, "note": null },
  "processing_ms": 431,
  "model": "baseline_B_regression_1789914685",
  "disclaimer": "Screening only, not a medical diagnosis..."
}
```

Validation & errors:
- Rejects files over `HEMOSENSE_MAX_UPLOAD_MB` (default 10) or non-image content types.
- Undecodable image → `400`.
- Model not loaded / missing → `503` with a clear reason.
- No face detected is **not** an error — the existing fallback crop is used and
  surfaced via `roi.note`, so the frontend can warn the user to re-frame the photo.

### 3.3 `POST /screen/roi`
Debug/visualization helper for the mobile frontend.

Takes the same upload, returns a `multipart`/binary response containing two PNG
images: `roi_raw.png` (extracted conjunctiva ROI) and `roi_corrected.png`
(fuzzy-corrected ROI), so the app can verify crop quality and guide the user to
re-take the photo if the crop is bad.

### 3.4 `POST /diet/recommendations`
Dietary Intelligence via any OpenAI-compatible LLM router (OpenRouter).

Accepts the screening result **or** an image to screen first, plus optional user
context:

```json
{
  "screening": {
    "predicted_hb_gdl": 11.3,
    "severity_class": "Mild",
    "anemic": true
  },
  "user_context": {
    "age": 29, "sex": "female", "pregnant": false,
    "diet": "vegetarian", "region": "India", "allergies": ["nuts"]
  },
  "model": null
}
```

If `screening` is omitted and `image` is provided, the API screens the image
first, then asks the LLM. The response always includes:

```json
{
  "recommendations": "... LLM-generated dietary guidance ...",
  "model_used": "deepseek/deepseek-r1:free",
  "attempts": ["deepseek/deepseek-r1:free", "meta-llama/llama-3.3-70b-instruct:free"],
  "failures": [{ "model": "...", "reason": "rate_limited(429)" }],
  "disclaimer": "..."
}
```

A fixed medical-safety disclaimer is appended to every response regardless of
what the LLM returns.

### 3.5 `GET /diet/usage`
In-process counters of LLM requests **per model** (and per day), so the user can
see when a free-tier daily limit is getting close.

```json
{
  "today": [ { "model": "deepseek/deepseek-r1:free", "requests": 34 } ],
  "last_hour": 3
}
```

---

## 4. OpenRouter LLM integration (`llm.py`)

**Why OpenRouter:** free-tier models are plentiful, the free roster rotates
monthly, and hitting a daily cap returns `429`. This makes a **priority-ordered
fallback chain** the right design.

- Base URL: `https://openrouter.ai/api/v1` (OpenAI-compatible `chat/completions`).
- Headers: `Authorization: Bearer $OPENROUTER_API_KEY`, plus `HTTP-Referer` and
  `X-Title` (recommended by OpenRouter).
- Model list: `HEMOSENSE_LLM_MODELS` env var, comma-separated, highest priority
  first. Sensible default:
  ```
  openrouter/free,
  deepseek/deepseek-r1:free,
  meta-llama/llama-3.3-70b-instruct:free,
  google/gemma-3-27b-it:free,
  openai/gpt-oss-20b:free,
  nvidia/llama-3.1-nemotron-ultra-253b:free
  ```
  (`openrouter/free` is the auto-router that picks any available free model.)
- **Fallback behavior:** try models in order. On `429` (free-tier limit hit),
  `5xx`, request timeout, or provider error, record the failure and move to the
  next model. If the whole chain fails → `503` with the failures listed.
- Per-request `model` override in `POST /diet/recommendations`: the client picks
  a first choice; the chain still provides fallback.
- `max_tokens` clamped to `HEMOSENSE_LLM_MAX_TOKENS` (default 600) to respect
  small free-tier budgets.
- **Security:** the API key is read from the environment only. It is never
  logged and never included in responses.

---

## 5. Configuration (`api/.env.example`)

```
# ---- Model / server ----
HEMOSENSE_MODEL_PATH=../scratch/saved_models/baseline_B_regression_1789914685_final.keras
HEMOSENSE_MAX_UPLOAD_MB=10

# ---- OpenRouter (Dietary Intelligence) ----
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
HEMOSENSE_LLM_MODELS=openrouter/free,deepseek/deepseek-r1:free,meta-llama/llama-3.3-70b-instruct:free,google/gemma-3-27b-it:free,openai/gpt-oss-20b:free,nvidia/llama-3.1-nemotron-ultra-253b:free
HEMOSENSE_LLM_MAX_TOKENS=600
HEMOSENSE_LLM_TIMEOUT_SECONDS=60

# ---- CORS (comma-separated origins; "*" for dev) ----
HEMOSENSE_CORS_ORIGINS=*
```

`.env` is loaded via `python-dotenv`; all values fall back to safe defaults.

---

## 6. Running

```powershell
# from the repo root (project env with tensorflow<2.17 installed)
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000
```

- Interactive API docs: http://localhost:8000/docs
- On a machine **without** the TF env, the API still starts; `POST /screen` and
  `POST /screen/roi` return `503 model_unavailable` with guidance, while
  `/health`, `/diet/recommendations`, and `/diet/usage` keep working.

---

## 7. Verification plan

1. Boot `uvicorn api.main:app` — confirm `/health` returns model metrics.
2. Upload one of the dataset conjunctiva images to `/screen` — confirm Hb,
   severity, and anemia flag are plausible vs. its `hemoglobin_level` label.
3. `POST /screen/roi` — confirm two PNGs come back.
4. `POST /diet/recommendations` with a screening payload and `diet="vegetarian"`
   — confirm an LLM response arrives with `model_used` and the disclaimer.
5. `GET /diet/usage` — confirm counters increment.
6. Remove the model path (or run without TF) — confirm `/screen` returns a clean
   `503` and `/health` reports `loaded: false`.

---

## 8. Known constraints / risks

- **Python/TF compatibility:** `tensorflow<2.17` excludes Python 3.13, so this
  machine (Python 3.13) cannot run CNN inference; the API degrades gracefully.
  Run inference on the project env (Python 3.11/3.12).
- **OpenRouter free roster changes monthly.** The default model list is a
  snapshot; `HEMOSENSE_LLM_MODELS` exists so it can be updated without code
  changes.
- **Free-tier caps (~20 req/min, 50–1000 req/day).** The fallback chain and
  `/diet/usage` counters mitigate day-to-day exhaustion.
- **Severe class is rare in the dataset (n≈1 in the test set).** Per-class
  recall for Severe is unreliable; responses do not claim per-class accuracy
  beyond what was measured.
- **Not a medical device.** Every response carries a disclaimer that the result
  is a screening estimate, not a diagnosis.