# HemoSense API

FastAPI backend for the HemoSense anemia-screening CNN + LLM Dietary Intelligence.

## Setup

```powershell
cd <repo root>

# 1. Install the web/API deps into your ML environment
#    (the ML stack is already pinned in scratch/requirements.txt)
pip install -r api/requirements.txt

# 2. Configure secrets & model
Copy-Item api/.env.example api/.env   # then edit api/.env (OpenRouter key, model list)

# 3. Run
uvicorn api.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `HEMOSENSE_MODEL_PATH` | `scratch/saved_models/baseline_B_regression_1789914685_final.keras` | Trained `.keras` model |
| `HEMOSENSE_META_PATH` | `scratch/results/baseline_B_regression_1789914685_meta.json` | Metrics shown by `/health` |
| `HEMOSENSE_MAX_UPLOAD_MB` | `10` | Upload size limit |
| `OPENROUTER_API_KEY` | — | OpenRouter key (Dietary Intelligence) |
| `HEMOSENSE_LLM_MODELS` | 6 free models, priority order | Comma-separated fallback chain |
| `HEMOSENSE_LLM_MAX_TOKENS` | `600` | Max completion tokens |
| `HEMOSENSE_LLM_TIMEOUT_SECONDS` | `60` | Per-model call timeout |
| `HEMOSENSE_CORS_ORIGINS` | `*` | CORS origins (dev) |

## Endpoints

- `GET  /health` — model status + saved test metrics.
- `POST /screen` — upload an eye/face photo → `predicted_hb_gdl`, `severity_class`,
  `anemic`, erythema indexes, latency, model name.
- `POST /screen/batch` — upload 2–10 photos (field `images`, repeated) + optional
  `data` JSON `{"user_context": {..., "symptoms": [...]}}` → per-photo results,
  aggregated verdict (median Hb, vote agreement, confidence), symptom report and a
  rule-based diet plan (`api/clinical.py`). Used by the React UI in `../frontend`.
- `GET  /symptoms` — symptom checklist (ids for `user_context.symptoms`).
- `POST /screen/roi` — upload a photo → raw + fuzzy-corrected conjunctiva ROI as
  base64 PNG data-URLs (for UI crop verification).
- `POST /diet/recommendations` — multipart form; either:
  - `data` (JSON) with a `screening` fragment + optional `user_context`, or
  - `image` (photo) to be screened first, plus optional `user_context`,
    `model` (preferred first-choice LLM), `max_tokens`.
- `GET  /diet/usage` — in-process per-model LLM request counters (daily/hourly).

## Examples

Screening:

```powershell
curl -F "image=@eye.jpg" http://localhost:8000/screen
```

Dietary recommendations (OpenRouter; fallback chain on 429/limits):

```powershell
curl -F 'data={"screening":{"predicted_hb_gdl":9.8,"severity_class":"Moderate","anemic":true},"user_context":{"diet":"vegetarian","sex":"female","age":29}}' http://localhost:8000/diet/recommendations
```

## Notes

- The API does **not** re-implement any pipeline code — it imports `../scratch`
  (`anemia_pipeline.py`, `evaluate.py`) and preprocesses images exactly like
  training (`data_loader._decode_and_resize`: 224x224, `/255.0`).
- **Python compatibility:** `tensorflow<2.17` requires Python 3.11/3.12. Without
  the TF env the app still boots; `/screen` and `/screen/roi` return `503` and
  `/health` reports `loaded: false`. `/diet/*` work standalone.
- Screening is an estimate, not a clinical diagnosis (disclaimer included).