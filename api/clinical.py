"""
clinical.py
Rule-based clinical layer on top of the ANFIS screening results.

  - aggregate_screenings(): combines 1-10 per-photo ANFIS probabilities into one
    screening verdict (median probability, vote agreement, confidence).
  - symptom_report():       symptoms typically associated with the detected
    severity, cross-checked against symptoms the patient reported.
  - baseline_diet_plan():   deterministic dietary plan used by the UI whenever
    the LLM (Dietary Intelligence) is unavailable, and as a structured summary.

Everything here is screening guidance only, never a diagnosis.
"""

import statistics
from typing import Dict, List, Optional

MIN_IMAGES = 1
MAX_IMAGES = 10

# Majority share of per-photo votes required before the verdict is called.
DECISION_AGREEMENT = 0.7

SEVERITY_ORDER = ["Normal", "Mild", "Moderate", "Severe"]
DISPLAY = {"Normal": "Normal", "Mild": "Mild", "Moderate": "Moderate-to-Severe",
           "Severe": "Moderate-to-Severe"}


# ---------------------------------------------------------------------------
# Aggregation of one or more photos (ANFIS probabilities)
# ---------------------------------------------------------------------------
def confidence_from_evidence(p: float, table: Optional[dict]) -> dict:
    """Confidence = accuracy the model actually achieved, in patient-level cross-validation,
    for patients whose result was equally clear (models/confidence.json)."""
    certainty = max(p, 1.0 - p)
    detail = {"certainty": round(certainty, 4), "cv_accuracy": None, "cv_n": 0,
              "basis": "No validation table loaded; confidence reflects certainty only."}
    label = "Low"
    for b in (table or {}).get("bins", []):
        if b["certainty_from"] <= certainty < b["certainty_to"] + 1e-9 and b["n"]:
            label = b["label"]
            detail.update(cv_accuracy=round(b["accuracy"], 4), cv_n=b["n"],
                          basis=(f"In patient-level cross-validation, {b['correct']} of {b['n']} patients "
                                 f"with a result this clear (certainty {b['certainty_from']:.1f}-"
                                 f"{min(b['certainty_to'], 1.0):.1f}) were classified correctly."))
            break
    return {"label": label, "detail": detail}


def aggregate_screenings(results: List[dict], confidence_table: Optional[dict] = None) -> dict:
    """results: successful per-image dicts from pipeline.screen_image_bytes.

    The verdict uses the median calibrated probability across photos against the
    model's threshold; agreement = share of photos that vote the same way."""
    n = len(results)
    p_a = statistics.median(r["p_anemic"] for r in results)
    p_s = statistics.median(r["p_moderate_or_severe"] for r in results)
    tau = results[0]["threshold"]
    anemic = p_a >= tau
    tau_s = results[0]["threshold_mod_sev"]
    severity = "Normal" if not anemic else ("Moderate" if p_s >= tau_s else "Mild")
    anemic_votes = sum(1 for r in results if r["anemic"])
    agreement = round(max(anemic_votes, n - anemic_votes) / n, 3)
    margin = abs(p_a - tau)

    conf = confidence_from_evidence(p_a, confidence_table)
    confidence, confidence_detail = conf["label"], conf["detail"]
    if n > 1 and agreement < DECISION_AGREEMENT:   # photos disagree: never claim more than Low
        confidence = "Low"
        confidence_detail["basis"] += f" The photos disagree ({anemic_votes} of {n} suggest anemia)."

    label = DISPLAY[severity]
    if n > 1 and agreement < DECISION_AGREEMENT:
        status = "inconclusive"
        headline = "Inconclusive - photos disagree"
        summary = (f"{anemic_votes} of {n} photos suggest anemia. Retake the photos in bright, even "
                   "light with the lower eyelid gently pulled down, or get a blood test.")
    elif anemic:
        status = "anemic"
        headline = f"Possible anemia ({label})"
        summary = ("The colour of the inner eyelid is in the range the model associates with "
                   f"anemia (risk score {p_a:.0%}). A blood test (CBC) is needed to confirm.")
    else:
        status = "normal"
        headline = "No sign of anemia"
        summary = ("The colour of the inner eyelid is in the range the model associates with "
                   f"normal haemoglobin (risk score {p_a:.0%}).")

    return {
        "predicted_hb_gdl": None,  # never estimated or shown
        "p_anemic": round(p_a, 4),
        "p_moderate_or_severe": round(p_s, 4),
        "threshold": tau,
        "severity_class": severity,
        "severity_label": label,
        "anemic": bool(anemic),
        "anemic_votes": anemic_votes,
        "n_used": n,
        "agreement": agreement,
        "confidence": confidence,
        "confidence_detail": confidence_detail,
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


def baseline_diet_plan(severity: str, user_context: Optional[Dict] = None) -> dict:
    """Personalised plan from real food-composition data (hemosense.diet, USDA FoodData Central)
    plus clinical guidance text for the grade."""
    from hemosense.diet import build_plan

    ctx = user_context or {}
    plan = build_plan(ctx, severity)
    extras = []
    if ctx.get("pregnant"):
        extras.append(f"Pregnancy raises the iron target to {plan['daily']['target_iron_mg']:g} mg/day: "
                      "take the iron and folic acid your doctor prescribes and attend antenatal blood tests.")
    if plan["diet_type"] == "vegan":
        extras.append("Include a vitamin B12 source (fortified foods or a supplement): "
                      "B12 deficiency also causes anemia.")
    if severity in ("Moderate", "Severe"):
        extras.append("Food alone is not enough to treat moderate or severe anemia. Ask your doctor about "
                      "iron, folate and B12; do not self-dose high-iron tablets.")
    d = plan["daily"]
    extras.append(f"This plan gives about {d['iron_mg']:g} mg iron (target {d['target_iron_mg']:g} mg, "
                  f"{d['target_basis']}) of which about {d['absorbable_iron_mg']:g} mg is absorbable.")
    return {
        "goal": _GOALS.get(severity, _GOALS["Normal"]),
        **plan,
        "extra_tips": extras,
        "when_to_see_clinician": _CLINICIAN.get(severity, _CLINICIAN["Normal"]),
        "recovery_outlook": (
            "With consistent diet and any prescribed treatment, hemoglobin usually rises "
            "about 1-2 g/dL every 2-3 weeks; recheck with a blood test after 4-8 weeks."
            if severity != "Normal" else
            "Keep a balanced, iron-rich diet and rescreen if symptoms appear."
        ),
    }
