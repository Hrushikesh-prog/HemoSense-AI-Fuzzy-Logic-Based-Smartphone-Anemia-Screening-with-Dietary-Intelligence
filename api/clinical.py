"""
clinical.py
Rule-based clinical layer on top of the CNN screening results.

  - aggregate_screenings(): combines 2-10 per-photo Hb estimates into one
    screening verdict (median Hb, vote agreement, confidence).
  - symptom_report():       symptoms typically associated with the detected
    severity, cross-checked against symptoms the patient reported.
  - baseline_diet_plan():   deterministic dietary plan used by the UI whenever
    the LLM (Dietary Intelligence) is unavailable, and as a structured summary.

Everything here is screening guidance only, never a diagnosis.
"""

import statistics
from typing import Dict, List, Optional

# Keep in sync with scratch/evaluate.py (ANEMIA_THRESHOLD, hb_to_severity bins)
ANEMIA_THRESHOLD = 12.0
MIN_IMAGES = 2
MAX_IMAGES = 10

# Majority share of per-photo votes required before the verdict is called.
DECISION_AGREEMENT = 0.7

SEVERITY_ORDER = ["Normal", "Mild", "Moderate", "Severe"]


def severity_for_hb(hb: float) -> str:
    """Same bins as evaluate.hb_to_severity (right-inclusive: (0,7], (7,10], (10,12], (12,30])."""
    if hb <= 7.0:
        return "Severe"
    if hb <= 10.0:
        return "Moderate"
    if hb <= 12.0:
        return "Mild"
    return "Normal"


# ---------------------------------------------------------------------------
# Aggregation of multiple photos
# ---------------------------------------------------------------------------
def aggregate_screenings(results: List[dict]) -> dict:
    """results: successful per-image screening dicts (predicted_hb_gdl, anemic, ...)."""
    hbs = [r["predicted_hb_gdl"] for r in results]
    n = len(hbs)
    median_hb = round(statistics.median(hbs), 2)
    std_hb = round(statistics.pstdev(hbs), 2) if n > 1 else 0.0

    anemic_votes = sum(1 for r in results if r["anemic"])
    majority = max(anemic_votes, n - anemic_votes)
    agreement = round(majority / n, 3)

    severity = severity_for_hb(median_hb)
    anemic = median_hb <= ANEMIA_THRESHOLD

    if agreement >= 0.8 and std_hb <= 1.0:
        confidence = "High"
    elif agreement >= DECISION_AGREEMENT and std_hb <= 1.8:
        confidence = "Medium"
    else:
        confidence = "Low"

    if agreement < DECISION_AGREEMENT:
        status = "inconclusive"
        headline = "Inconclusive - photos disagree"
        summary = (f"{anemic_votes} of {n} photos suggest anemia. Retake photos in even, "
                   "natural light with the lower eyelid gently pulled down, or get a blood test.")
    elif anemic:
        status = "anemic"
        headline = f"Anemia likely ({severity})"
        summary = (f"Estimated hemoglobin {median_hb} g/dL is at or below the "
                   f"{ANEMIA_THRESHOLD:g} g/dL screening threshold; "
                   f"{anemic_votes} of {n} photos agree.")
    else:
        status = "normal"
        headline = "No anemia detected"
        summary = (f"Estimated hemoglobin {median_hb} g/dL is above the "
                   f"{ANEMIA_THRESHOLD:g} g/dL screening threshold; "
                   f"{n - anemic_votes} of {n} photos agree.")

    return {
        "predicted_hb_gdl": median_hb,
        "mean_hb_gdl": round(statistics.fmean(hbs), 2),
        "std_hb_gdl": std_hb,
        "min_hb_gdl": round(min(hbs), 2),
        "max_hb_gdl": round(max(hbs), 2),
        "severity_class": severity,
        "anemic": anemic,
        "anemic_votes": anemic_votes,
        "n_used": n,
        "agreement": agreement,
        "confidence": confidence,
        "verdict": {"status": status, "headline": headline, "summary": summary},
    }


# ---------------------------------------------------------------------------
# Symptoms
# ---------------------------------------------------------------------------
# id -> label; ids are what the UI sends back.
SYMPTOMS = {
    "fatigue": "Tiredness / fatigue",
    "weakness": "General weakness",
    "pale_skin": "Pale skin, lips or nail beds",
    "breathless_exertion": "Shortness of breath on exertion",
    "dizziness": "Dizziness or light-headedness",
    "headache": "Frequent headaches",
    "cold_extremities": "Cold hands and feet",
    "fast_heartbeat": "Fast or irregular heartbeat",
    "brittle_nails": "Brittle or spoon-shaped nails",
    "hair_loss": "Hair loss",
    "sore_tongue": "Sore or smooth tongue",
    "pica": "Cravings for ice, clay or starch (pica)",
    "restless_legs": "Restless legs",
    "poor_concentration": "Poor concentration",
    "chest_pain": "Chest pain",
    "fainting": "Fainting",
    "breathless_rest": "Shortness of breath at rest",
}

# Symptoms that need prompt medical attention whatever the photo says.
RED_FLAGS = {"chest_pain", "fainting", "breathless_rest"}

EXPECTED_BY_SEVERITY = {
    "Normal": [],
    "Mild": ["fatigue", "weakness", "poor_concentration", "pale_skin"],
    "Moderate": ["fatigue", "weakness", "pale_skin", "breathless_exertion", "dizziness",
                 "headache", "cold_extremities", "brittle_nails", "fast_heartbeat"],
    "Severe": ["fatigue", "weakness", "pale_skin", "breathless_exertion", "dizziness",
               "headache", "cold_extremities", "fast_heartbeat", "brittle_nails",
               "sore_tongue", "pica", "chest_pain", "fainting", "breathless_rest"],
}


def symptom_catalog() -> List[dict]:
    return [{"id": k, "label": v, "red_flag": k in RED_FLAGS} for k, v in SYMPTOMS.items()]


def symptom_report(severity: str, reported: Optional[List[str]]) -> dict:
    reported = [s for s in (reported or []) if s in SYMPTOMS]
    expected = EXPECTED_BY_SEVERITY.get(severity, [])
    matched = [s for s in reported if s in expected]
    red = [s for s in reported if s in RED_FLAGS]

    if not reported:
        concordance = "not_reported"
        note = "No symptoms were reported; the result is based on the photos only."
    elif severity == "Normal":
        concordance = "discordant"
        note = ("Symptoms were reported although the photos look normal. Symptoms like these "
                "can have other causes - a blood test (CBC) is the reliable check.")
    elif matched:
        concordance = "concordant"
        note = (f"{len(matched)} of your reported symptoms are typical of "
                f"{severity.lower()} anemia, which supports the screening result.")
    else:
        concordance = "discordant"
        note = "Your reported symptoms are not typical of this severity level."

    def _items(ids):
        return [{"id": s, "label": SYMPTOMS[s], "red_flag": s in RED_FLAGS} for s in ids]

    return {
        "expected": _items(expected),
        "reported": _items(reported),
        "matched": _items(matched),
        "red_flags": _items(red),
        "concordance": concordance,
        "note": note,
        "urgent": bool(red) or severity == "Severe",
    }


# ---------------------------------------------------------------------------
# Baseline diet plan (deterministic, no LLM)
# ---------------------------------------------------------------------------
_IRON_FOODS = {
    "omnivore": [
        "Lean red meat, liver (once a week), chicken and fish - heme iron is absorbed best",
        "Eggs, especially with a vitamin C side",
        "Lentils, chickpeas, kidney beans and rajma",
        "Spinach, amaranth, moringa and other dark leafy greens",
        "Dates, raisins, figs and jaggery in small portions",
    ],
    "vegetarian": [
        "Lentils (dal), chickpeas, kidney beans, soybeans and tofu",
        "Spinach, amaranth, moringa (drumstick) leaves and fenugreek",
        "Iron-fortified cereals, ragi, bajra and poha",
        "Pumpkin, sesame and flax seeds; peanuts and cashews",
        "Dates, raisins, figs and jaggery; eggs if you eat them",
    ],
    "vegan": [
        "Lentils, chickpeas, kidney beans, soybeans, tofu and tempeh",
        "Spinach, amaranth, moringa leaves, kale and fenugreek",
        "Iron-fortified cereals, ragi, bajra, quinoa and poha",
        "Pumpkin, sesame (tahini) and flax seeds; cashews",
        "Dates, raisins, dried apricots, figs and blackstrap molasses",
    ],
}

_VITAMIN_C = [
    "Citrus fruits (orange, sweet lime), amla (Indian gooseberry), guava",
    "Tomatoes, bell peppers, lemon juice squeezed over dal or greens",
    "Strawberries, kiwi, papaya, broccoli",
]

_AVOID = [
    "Tea and coffee within 1 hour before or after iron-rich meals (tannins block absorption)",
    "Calcium supplements or large amounts of milk together with iron-rich meals",
    "Heavily processed foods and excess sugar that replace nutrient-dense meals",
]

_MEALS = {
    "omnivore": {
        "Breakfast": "Vegetable omelette + whole-wheat toast + a glass of orange juice",
        "Lunch": "Grilled chicken or fish, spinach dal, brown rice, tomato-cucumber salad with lemon",
        "Snack": "Handful of dates and pumpkin seeds + a guava",
        "Dinner": "Lean mutton or egg curry, rajma, roti and a bell-pepper stir-fry",
    },
    "vegetarian": {
        "Breakfast": "Ragi or fortified-cereal porridge with raisins + a glass of amla or orange juice",
        "Lunch": "Palak dal, brown rice or bajra roti, beetroot-tomato salad with lemon",
        "Snack": "Roasted chana + jaggery piece + a guava or orange",
        "Dinner": "Paneer or tofu with spinach, rajma or chole, roti, lemon on the side",
    },
    "vegan": {
        "Breakfast": "Poha with peanuts and lemon + fortified plant milk + a kiwi or orange",
        "Lunch": "Chickpea-spinach curry, quinoa or brown rice, tomato-pepper salad with lemon",
        "Snack": "Dates, dried apricots and pumpkin seeds + a guava",
        "Dinner": "Tofu and kale stir-fry with sesame, lentil soup, whole-grain roti",
    },
}

_CLINICIAN = {
    "Normal": "Routine check-up once a year, or sooner if you develop symptoms.",
    "Mild": "Book a blood test (CBC + ferritin) within 2-4 weeks to confirm and find the cause.",
    "Moderate": ("See a doctor within a week. A blood test is needed, and iron supplements "
                 "are often prescribed alongside diet changes."),
    "Severe": ("Seek medical care as soon as possible (within 24-48 hours). Severe anemia "
               "usually needs treatment beyond diet, such as supplements, infusions or transfusion."),
}

_GOALS = {
    "Normal": "Maintain healthy iron stores and prevent anemia.",
    "Mild": "Rebuild iron stores through daily iron-rich meals paired with vitamin C.",
    "Moderate": "Maximise iron intake and absorption at every meal while medical treatment is arranged.",
    "Severe": "Support recovery alongside urgent medical treatment - diet alone is not enough.",
}


def _normalise_diet(diet: Optional[str]) -> str:
    d = (diet or "").strip().lower()
    if d in ("vegan", "plant-based", "plant based"):
        return "vegan"
    if d in ("vegetarian", "veg", "eggetarian", "lacto-vegetarian", "jain"):
        return "vegetarian"
    return "omnivore"


def baseline_diet_plan(severity: str, user_context: Optional[Dict] = None) -> dict:
    ctx = user_context or {}
    diet = _normalise_diet(ctx.get("diet"))
    allergies = [a.strip().lower() for a in (ctx.get("allergies") or []) if a and a.strip()]

    def _safe(items):
        if not allergies:
            return list(items)
        return [i for i in items if not any(a in i.lower() for a in allergies)]

    extras = []
    if ctx.get("pregnant"):
        extras.append("Pregnancy raises iron needs to ~27 mg/day - take prescribed iron and "
                      "folic acid supplements and attend antenatal blood tests.")
    if (ctx.get("sex") or "").lower() == "female" and not ctx.get("pregnant"):
        extras.append("Menstruation increases iron losses - keep iron-rich foods in every day's meals.")
    if diet == "vegan":
        extras.append("Include a vitamin B12 source (fortified foods or a supplement) - "
                      "B12 deficiency also causes anemia.")
    if severity in ("Moderate", "Severe"):
        extras.append("Ask your doctor about iron, folate and B12 supplements; do not self-dose high-iron tablets.")

    return {
        "goal": _GOALS.get(severity, _GOALS["Normal"]),
        "diet_type": diet,
        "iron_rich_foods": _safe(_IRON_FOODS[diet]),
        "pair_with_vitamin_c": _safe(_VITAMIN_C),
        "avoid_or_limit": _AVOID,
        "sample_day": {k: v for k, v in _MEALS[diet].items() if v in _safe([v])},
        "extra_tips": extras,
        "when_to_see_clinician": _CLINICIAN.get(severity, _CLINICIAN["Normal"]),
        "recovery_outlook": (
            "With consistent diet and any prescribed treatment, hemoglobin usually rises "
            "about 1-2 g/dL every 2-3 weeks; recheck with a blood test after 4-8 weeks."
            if severity != "Normal" else
            "Keep a balanced, iron-rich diet and rescreen if symptoms appear."
        ),
    }
