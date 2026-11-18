# HemoSense UI (Next.js)

A standalone Next.js (App Router) + React frontend for the HemoSense API (`../api`).

**Flow:** upload 2–10 lower-eyelid photos, optionally add patient details and symptoms,
then click **Analyse**. The UI shows:

- the combined verdict (anemia likely / no anemia / inconclusive), estimated Hb,
  severity, confidence and photo agreement on a severity-banded Hb gauge
- the symptoms typical for that severity, cross-checked against the reported symptoms,
  with red-flag warnings
- a recovery diet plan: a rule-based plan (always shown) plus an AI-personalised plan
  from `/diet/recommendations`
- a per-photo breakdown with the fuzzy-corrected conjunctiva ROI thumbnails

## Run

```powershell
# 1. API (repo root, in the TF environment - see api/README.md)
uvicorn api.main:app --host 127.0.0.1 --port 8000

# 2. UI
cd frontend
npm install
npm run dev          # http://localhost:3000
```

In dev the Next.js server rewrites `/api/*` to `http://127.0.0.1:8000`, so CORS is
not involved. To point at another backend, set `HEMOSENSE_API_TARGET` (rewrite
target) or `NEXT_PUBLIC_API_URL` (skips the rewrite, e.g. for `npm run build`
deployments).

## Structure

```
src/
  app/
    layout.jsx                 metadata, fonts, global styles
    page.jsx                   renders the screening page
  api.js                       fetch client (/health, /symptoms, /screen/batch, /diet/recommendations)
  App.jsx                      page state: inputs -> results ('use client')
  components/
    Header.jsx                 model / LLM status badges
    PhotoUploader.jsx          drag-drop, file picker, camera capture, 2-10 validation
    PatientForm.jsx            age, sex, pregnancy, diet, region, allergies, symptom chips
    Results.jsx                verdict, urgent alert, per-photo grid, print
    HbGauge.jsx                Hb scale with the model's severity bands
    SymptomsPanel.jsx          expected vs reported symptoms
    DietPanel.jsx              rule-based plan + AI markdown plan
```
