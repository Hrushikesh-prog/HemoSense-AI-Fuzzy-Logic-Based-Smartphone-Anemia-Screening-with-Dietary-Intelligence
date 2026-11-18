# HemoSense AI: the app end to end

Last updated: 2026-11-17. This document follows one screening from the user's hand to the result on
screen, and states **where every number shown in the app comes from**. Nothing the user sees is a
placeholder: each value is measured from the photo, produced by the trained model, computed from
validation results, or read from a cited food database.

---

## 1. What the user experiences

| # | Screen | What happens | Data it uses |
|---|---|---|---|
| 1 | Splash, onboarding, consent | Explains screening vs diagnosis; consent is stored on the phone | none |
| 2 | Profile | Age, sex, pregnancy, diet type, allergies | stored on the phone (Hive) |
| 3 | Capture tutorial (first time, then from the guide) | Animated steps: bright light or torch, **look up**, **gently pull the lower eyelid down** so the pink half-moon shows, hold 10-15 cm away, draw the box around the half-moon | none (instructional) |
| 4 | Capture guide + symptom checklist | Optional symptoms (fatigue, breathlessness, ...) | `GET /symptoms` |
| 5 | Camera | Torch on, ~0.8 s for exposure to settle, then 3 frames 0.35 s apart; or 1-3 photos from the gallery | phone camera |
| 6 | Review | Photo at its real aspect ratio; the user drags/resizes **one box** over the pink half-moon (shared by the 3 burst frames); "Analyse" stays disabled until the box is placed | user input |
| 7 | Analysing | Upload and server processing (about 1.5 s per photo) | `POST /screen/batch` |
| 8 | Result | Grade (Normal / Mild / Moderate-to-Severe), anemia risk %, confidence with its evidence, photo agreement, see-a-doctor banner for moderate/severe or red-flag symptoms | server response |
| 9 | Why this result? | The detected eyelid (green tint), the 3 features with Low/Medium/High membership bars, the top 3 IF-THEN fuzzy rules, the confidence basis | server response |
| 10 | Diet | Questionnaire (budget, state, living situation, kitchen, dislikes, routine), then a personalised one-day plan: dish, time, foods, grams, iron and absorbable iron per meal, AI cost estimate, replacements for dislikes, daily total vs target | `POST /diet/plan` (AI + USDA data, rules fallback) |
| 11 | History | Past grades and risk scores, stored only on the phone | Hive |
| 12 | Settings | Backend URL + connection test | `GET /health` |

If a photo cannot be analysed the user gets a specific reason and a fix (section 4.2), never a guessed result.

---

## 2. Architecture

```
Phone (Flutter app)                      AWS ap-south-1 (EC2 t3.small, Docker Compose)
  profile, history (Hive)                 Caddy  (TLS, Let's Encrypt, 40 MB limit)
  camera / gallery  ──photo + box──HTTPS──▶ FastAPI api/ (2 workers, non-root)
  review box                                 └─ shared core hemosense/
  result, why, diet  ◀──────JSON────────        segment.py  quality gate, GrabCut, shape + eye checks
                                                 features.py EI, a*, HHR, saturation
                                                 anfis.py    ANFIS inference (numpy)
                                                 diet.py     meal planner (USDA data)
                                               models/anfis.json, models/confidence.json
                                               hemosense/data/foods_usda.csv
Optional: OpenRouter LLM for diet wording (falls back to the rule-based plan).
```

The same `hemosense/` package is used by the research experiments and by the server, so the
evaluated pipeline is the deployed pipeline.

---

## 3. The request

`POST /screen/batch` (multipart)

- `images`: 1-10 JPEG/PNG files (max 10 MB each)
- `data`: JSON `{"user_context": {"age", "sex", "pregnant", "diet", "allergies", "symptoms"}, "roi_boxes": [[x, y, w, h], ...]}`;
  boxes are fractions (0-1) of the photo as displayed (EXIF-rotated).

Photos are processed in memory and never written to disk on the server.

---

## 4. Server pipeline, step by step (per photo)

### 4.1 Decode
Pillow opens the image and applies the EXIF orientation, so the user's box lines up with the pixels.
The image is downscaled to at most 900 px on the long side for processing.

### 4.2 Rejections (each returns a code and a human message)

| Code | Rule | Where the threshold comes from |
|---|---|---|
| `too_far` | box shorter side < 40 px | below this the eyelid is a few pixels tall |
| `too_dark` | mean brightness in the box < 0.15 | quality gate design |
| `overexposed` | > 25 % of box pixels clipped | quality gate design |
| `blurry` | Laplacian variance < 12 (at 320 px width) | quality gate design |
| `no_conjunctiva` | fewer than max(150 px, 2 % of box) tissue pixels after segmentation | segmentation design |
| `not_crescent` | the region is not half-moon shaped: elongation (length^2/area) < 2.7, or solidity > 0.85, or width/height < 1.1 | measured on all 215 dataset photos: real eyelids always had elongation >= 2.9, solidity <= 0.80, width/height >= 1.24 |
| `no_eye` | no white of the eye (bright, low-saturation region) just above the box | a pulled-down eyelid always sits under the sclera |
| `bad_image` | file cannot be decoded | - |

### 4.3 Segmentation
GrabCut runs inside the user's box (on a crop with 15 % margin, at most 360 px, 4 iterations).
Colour refinement removes dark lashes, specular glare and pale sclera, then splits the remaining
pixels by smoothed CIELAB a* (Otsu) when there are two clear colour populations. The largest
half-moon-shaped region is kept. Measured against expert masks on 215 dataset photos with simulated
user boxes: median Dice 0.82.

### 4.4 Features (computed from the segmented pixels of this photo)

| Feature shown in the app | Definition | Origin |
|---|---|---|
| Redness (erythema index, EI) | 100 x (log10 mean R - log10 mean G) | Collings et al. 2016 |
| Red-green balance (CIELAB a*) | mean a* of the tissue pixels | standard colour science |
| Share of strongly red pixels (HHR) | share of pixels with hue within +/-15 deg of red and saturation > 0.30 | Zhao et al. 2024 |
| Colour saturation | mean HSV saturation | standard colour science |

### 4.5 Model: ANFIS
Two zero-order Sugeno ANFIS models from `models/anfis.json`: one for "anemic" and one for
"moderate or severe". Each takes 3 features (a*, HHR, EI), 3 Gaussian terms each (Low / Medium /
High), 27 rules (21-22 active), 45 parameters, then Platt calibration to a probability.
Decision rule: probability >= 0.5. Trained on 215 patients of the Eyes-defy-anemia dataset with
patient-level validation (cross-validated AUC 0.879, 95 % CI 0.829-0.922).
The membership bars and IF-THEN rules in "Why this result?" are this model's actual values for
the photo.

### 4.6 Combining photos
Median probability across the accepted photos; agreement = share of photos voting the same way.
Grade: Normal if p < 0.5; otherwise Moderate-to-Severe if the second model's p >= 0.5, else Mild.

### 4.7 Confidence (evidence-based)
`models/confidence.json` holds how often the model was right in patient-level cross-validation,
grouped by certainty = max(p, 1 - p):

| Certainty | Patients | Correct | Label |
|---|---|---|---|
| 0.5-0.6 | 28 | 50 % | Low |
| 0.6-0.7 | 26 | 65 % | Low |
| 0.7-0.8 | 20 | 70 % | Low |
| 0.8-0.9 | 72 | 85 % | Medium |
| 0.9-1.0 | 69 | 94 % | High |

The app shows the label and the sentence behind it, e.g. "61 of 72 patients with a result this
clear were classified correctly". If the photos disagree (fewer than 70 % agree) confidence is Low.

### 4.8 Diet plan
`hemosense/diet.py` builds a one-day plan for this person and this grade:

- **Food data:** 46 foods common in Indian diets, every nutrient value (iron, vitamin C, calcium,
  protein, energy per 100 g) and every serving weight read from **USDA FoodData Central SR Legacy**
  (public domain), each with its FDC id (`hemosense/data/foods_usda.csv`, built by
  `research/build_food_table.py`). Labels name the USDA food exactly (e.g. "Millet, cooked (proso
  millet)", "Atlantic mackerel") so no Indian food is mislabelled.
- **Personalisation:** diet type (vegan / vegetarian / eggetarian / omnivore), allergies, sex, age,
  pregnancy (liver excluded in pregnancy: high vitamin A), and the date (plans vary day to day).
- **Target:** iron RDA by sex, age and pregnancy (US NIH Office of Dietary Supplements: women
  19-50 18 mg, men 8 mg, pregnancy 27 mg; verify against ICMR-NIN 2020 for Indian use).
- **Absorption model:** absorbable = heme x 0.25 + non-heme x 0.10 x E x I; E = 2 when the meal has
  >= 25 mg vitamin C or meat/fish; I = 0.7 when the meal has >= 300 mg calcium, x 0.8 for
  phytate-rich foods without an enhancer (Hurrell & Egli 2010 ranges).
- **Assembly:** each meal slot picks the allowed food that adds the most absorbable iron; extra
  servings are added until the RDA is met. Tea, coffee and dairy are kept out of iron meals, and the
  plan states their effect from the same data (e.g. "Milk: 276 mg calcium per cup").
- Clinical guidance text (goal, when to see a clinician, recovery outlook) depends on the grade.

### 4.9 Diet questionnaire and the AI planner (`POST /diet/plan`)
The Diet tab asks once (editable later): daily budget in Rs, state/UT and city, living situation
(urban / rural / hostel-PG), kitchen (cook at home / shared / none) and fridge, dislikes (from
`GET /diet/foods` or typed), skips breakfast, night shift. These travel as `user_context.diet_profile`.

- **Rules applied with data:** dislikes are removed and each gets a replacement from the same food
  group with the closest iron and vitamin C per serving (the reason quotes the USDA numbers); a dislike
  that is not in the food list is simply never suggested. Skipping breakfast removes that meal; night
  shift shifts meal times; no fridge removes fresh meat and fish.
- **AI planner:** the server sends the AI the person's answers, the grade, the iron target and the
  list of allowed foods (FDC id + USDA numbers). The AI proposes meals, local dish names for the
  state, meal times and **estimated ingredient costs**. The server then **rejects** any food that is
  not allowed (diet, allergy, dislike, pregnancy) and **recomputes every nutrient** from USDA data.
  Costs are always labelled "AI estimate of local retail prices ...; not official prices", and a
  warning appears if the estimate exceeds the budget.
- **Fallback:** if the AI is unavailable or its answer fails validation, the rule-based planner
  answers and the app shows "Data-driven plan (AI unavailable)".
- AI provider: OpenRouter (key in `api/.env`). **Status 2026-11-17:** the configured key is rejected
  by OpenRouter (401), so plans currently come from the rule-based planner; a new key (or Amazon
  Bedrock) enables the AI path with no app change.

---

## 5. Where every number comes from

| Shown in the app | Source |
|---|---|
| Risk %, grade | ANFIS output for this photo (`models/anfis.json`) |
| Confidence label and sentence | patient-level cross-validation table (`models/confidence.json`) |
| Photo agreement | votes of this user's photos |
| Feature values and membership bars | computed from this photo's segmented eyelid |
| IF-THEN rules and their risk | the trained model's rules that fire most for this photo |
| Detected-eyelid image | this photo with the segmentation tinted |
| Foods, grams, iron, vitamin C, calcium | USDA FoodData Central (FDC id per food) |
| Absorbable iron | absorption model applied to those USDA values |
| Dish names, meal times, Rs costs | AI planner, costs labelled as AI estimates (not official prices) |
| Dislike replacements | closest food in the same group by USDA iron and vitamin C |
| Daily iron target | NIH ODS RDA for the user's sex/age/pregnancy |
| Symptom list | server catalogue (`GET /symptoms`) |
| History | the user's own past results on the phone |

No exact haemoglobin value is ever estimated or shown.

---

## 6. Response (abridged)

```json
{
  "aggregate": {"p_anemic": 0.88, "severity_class": "Moderate", "severity_label": "Moderate-to-Severe",
                "anemic": true, "n_used": 3, "agreement": 1.0, "confidence": "Medium",
                "confidence_detail": {"certainty": 0.88, "cv_accuracy": 0.847, "cv_n": 72, "basis": "..."},
                "verdict": {"status": "anemic", "headline": "...", "summary": "..."}},
  "per_image": [{"p_anemic": 0.88, "features": {"ei": 24.1, "a": 31.2, "hhr": 0.21, "sat": 0.44},
                 "explanation": {"inputs": ["a", "hhr", "ei"], "memberships": {...}, "top_rules": [...]},
                 "roi_thumbnail": "data:image/png;base64,...", "quality": {...}}],
  "symptoms": {...},
  "diet_plan": {"meals": [{"meal": "Lunch", "items": [{"food": "...", "grams": 177, "iron_mg": 5.2,
                 "fdc_id": 175194}], "absorbable_iron_mg": 2.2, "note": "..."}],
                "daily": {"iron_mg": 25.5, "target_iron_mg": 18, "target_basis": "RDA, women 19-50 (NIH ODS)"},
                "data_source": "USDA FoodData Central, SR Legacy 2018-04 (public domain)"},
  "disclaimer": "Screening only, not a diagnosis. ..."
}
```

---

## 7. Deployment and operations

| Item | Value |
|---|---|
| URL | `https://3-111-237-63.sslip.io` (fallback `http://3.111.237.63`) |
| Host | AWS EC2 t3.small, Ubuntu 24.04, encrypted disk, IMDSv2, Elastic IP, Mumbai |
| Containers | `caddy` (TLS) + `api` (FastAPI, uvicorn x2, non-root, health-checked) |
| Resilience | CloudWatch auto-recover alarm; containers restart automatically |
| Access | ports 80/443 public, SSH only from the deployer's IP; least-privilege IAM policy |
| Deploy / update | `bash deploy/aws_deploy.sh` (idempotent) |
| Remove | `bash deploy/aws_teardown.sh` |
| Cost | about USD 0.025 per hour while running |

## 8. Privacy and safety
- No login, no account; photos are processed in memory and not stored on the server.
- History, profile and consent stay on the phone.
- "Screening only, not a diagnosis" on every result, diet and history screen.
- See-a-doctor banner for moderate/severe results and red-flag symptoms.
- The diet plan tells moderate/severe users that food alone is not treatment.

## 9. Quality checks
- 45 Python tests: features, ANFIS gradients, Mamdani, metrics, segmentation and every rejection
  rule, API end to end (real photo, multi-photo, bad photos, EXIF), diet traceability to USDA,
  diet personalisation (vegan, allergies, pregnancy), confidence from the CV table.
- Flutter: `flutter analyze` clean, widget tests for parsing, the box editor and the result views.

## 10. Known limitations
- Trained and validated on one public dataset (215 adults, India and Italy); no prospective phone
  study yet; within-India AUC is lower (about 0.65).
- No colour reference card; lighting differences can shift colour (sclera-based white balance is
  prepared as future work).
- The user must draw the box; automatic segmentation (U-Net) is future work.
- USDA foods are ingredients, not Indian cooked dishes; RDA values are US (NIH) and should be
  checked against ICMR-NIN 2020.
