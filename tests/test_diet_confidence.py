"""Diet engine (real USDA data, personalised) and evidence-based confidence."""

import datetime as dt
import json
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api.clinical import aggregate_screenings, confidence_from_evidence  # noqa: E402
from hemosense.diet import build_plan  # noqa: E402

DAY = dt.date(2026, 11, 18)
FOODS = pd.read_csv(os.path.join(ROOT, "hemosense", "data", "foods_usda.csv"))


def _items(plan):
    return [i for m in plan["meals"] for i in m["items"]]


def test_every_number_traces_to_usda_row():
    plan = build_plan({"sex": "female", "age": 24, "diet": "vegetarian"}, "Mild", DAY)
    for it in _items(plan):
        row = FOODS[FOODS.fdc_id == it["fdc_id"]].iloc[0]
        k = row.serving_grams / 100
        assert it["iron_mg"] == pytest.approx(row.iron_mg * k, abs=0.01)
        assert it["vitamin_c_mg"] == pytest.approx(row.vitamin_c_mg * k, abs=0.1)
        assert it["grams"] == round(row.serving_grams)


def test_plans_differ_by_profile_and_day():
    a = build_plan({"sex": "female", "age": 24, "diet": "vegetarian"}, "Mild", DAY)
    b = build_plan({"sex": "male", "age": 30, "diet": "omnivore"}, "Normal", DAY)
    c = build_plan({"sex": "female", "age": 24, "diet": "vegetarian"}, "Mild", DAY + dt.timedelta(days=1))
    assert a["sample_day"] != b["sample_day"]
    assert a["sample_day"] != c["sample_day"]
    assert a["daily"]["target_iron_mg"] == 18 and b["daily"]["target_iron_mg"] == 8


def test_vegan_plan_has_no_animal_or_dairy_foods():
    plan = build_plan({"sex": "female", "age": 28, "diet": "vegan"}, "Moderate", DAY)
    groups = {i["group"] for i in _items(plan)}
    assert not groups & {"meat", "fish", "egg", "dairy"}


def test_allergies_respected():
    plan = build_plan({"sex": "female", "age": 28, "diet": "vegan", "allergies": ["peanut", "sesame", "soy"]},
                      "Mild", DAY)
    names = " ".join(i["food"].lower() for i in _items(plan))
    assert "peanut" not in names and "sesame" not in names and "tofu" not in names


def test_pregnancy_excludes_liver_and_raises_target():
    plan = build_plan({"sex": "female", "age": 26, "pregnant": True, "diet": "omnivore"}, "Mild", DAY)
    assert all("liver" not in i["food"].lower() for i in _items(plan))
    assert plan["daily"]["target_iron_mg"] == 27


def test_every_meal_with_plant_iron_has_vitamin_c_or_heme():
    plan = build_plan({"sex": "female", "age": 24, "diet": "vegetarian"}, "Mild", DAY)
    for m in plan["meals"]:
        assert any(i["vitamin_c_mg"] >= 10 or i["heme"] for i in m["items"]), m["meal"]


def test_tea_and_dairy_never_inside_meals():
    plan = build_plan({"sex": "male", "age": 30, "diet": "omnivore"}, "Normal", DAY)
    assert not {i["group"] for i in _items(plan)} & {"beverage_inhib", "dairy"}


# ---------------- confidence
TABLE = json.load(open(os.path.join(ROOT, "models", "confidence.json"), encoding="utf-8"))


@pytest.mark.parametrize("p,label", [(0.97, "High"), (0.03, "High"), (0.85, "Medium"), (0.55, "Low"), (0.45, "Low")])
def test_confidence_comes_from_cv_table(p, label):
    c = confidence_from_evidence(p, TABLE)
    assert c["label"] == label
    assert c["detail"]["cv_n"] > 0 and 0 <= c["detail"]["cv_accuracy"] <= 1


def test_disagreeing_photos_force_low_confidence():
    base = {"threshold": 0.5, "threshold_mod_sev": 0.5, "p_moderate_or_severe": 0.1}
    res = [dict(base, p_anemic=0.97, anemic=True, severity_class="Mild"),
           dict(base, p_anemic=0.03, anemic=False, severity_class="Normal"),
           dict(base, p_anemic=0.04, anemic=False, severity_class="Normal")]
    agg = aggregate_screenings(res, TABLE)
    assert agg["confidence"] == "Low"


# ---------------- questionnaire + AI planner
from hemosense.diet import allowed_pool, evaluate_spec  # noqa: E402

PROFILE = {"sex": "female", "age": 24, "diet": "vegetarian",
           "diet_profile": {"budget_inr_per_day": 150, "state": "Tamil Nadu", "area_type": "urban",
                            "kitchen": "home", "fridge": True, "dislikes": ["spinach", "bitter gourd"],
                            "skips_breakfast": True}}


def test_dislikes_removed_with_data_based_replacement():
    plan = build_plan(PROFILE, "Mild", DAY)
    assert all("spinach" not in i["food"].lower() for i in _items(plan))
    reps = {r["disliked"]: r for r in plan["replacements"]}
    sp = next(r for k, r in reps.items() if "spinach" in k.lower())
    assert sp["replacement"] and "USDA" in sp["reason"]
    assert reps["bitter gourd"]["replacement"] is None          # not in the food list


def test_skips_breakfast_and_no_fridge():
    plan = build_plan(PROFILE, "Mild", DAY)
    assert [m["meal"] for m in plan["meals"]] == ["Lunch", "Snack", "Dinner"]
    ctx = {"sex": "male", "age": 30, "diet": "omnivore", "diet_profile": {"fridge": False}}
    assert not {i["group"] for i in _items(build_plan(ctx, "Normal", DAY))} & {"meat", "fish"}


def _spec(ok):
    ids = {g: int(ok[ok.group == g].fdc_id.iloc[0]) for g in ("grain", "legume", "fruit_c", "nuts_seeds")}
    return {"meals": [
        {"meal": "Lunch", "time": "1:00 pm", "dish": "Rajma rice", "est_cost_inr": 60,
         "items": [{"fdc_id": ids["grain"], "servings": 1}, {"fdc_id": ids["legume"], "servings": 1.5},
                   {"fdc_id": ids["fruit_c"], "servings": 1}]},
        {"meal": "Snack", "time": "4:30 pm", "dish": "Seeds and fruit", "est_cost_inr": 30,
         "items": [{"fdc_id": ids["nuts_seeds"], "servings": 1}, {"fdc_id": ids["fruit_c"], "servings": 1}]},
        {"meal": "Dinner", "time": "8:00 pm", "dish": "Dal and roti", "est_cost_inr": 50,
         "items": [{"fdc_id": ids["legume"], "servings": 1}, {"fdc_id": ids["fruit_c"], "servings": 1}]}],
        "tips": ["Buy greens at the morning market."]}


def test_ai_spec_numbers_are_recomputed_and_cost_labelled():
    ok, _, _ = allowed_pool(PROFILE)
    plan = evaluate_spec(PROFILE, _spec(ok), ai_model="test-model", day=DAY)
    assert plan["generated_by"] == "ai" and plan["daily"]["est_cost_inr"] == 140
    assert "AI estimate" in plan["cost_basis"] and "not official" in plan["cost_basis"]
    for it in _items(plan):
        row = FOODS[FOODS.fdc_id == it["fdc_id"]].iloc[0]
        assert it["iron_mg"] == pytest.approx(row.iron_mg * row.serving_grams * it["servings"] / 100, abs=0.01)


def test_ai_spec_with_foreign_or_disliked_food_is_rejected():
    ok, _, _ = allowed_pool(PROFILE)
    bad = _spec(ok)
    bad["meals"][0]["items"].append({"fdc_id": 99999999, "servings": 1})
    with pytest.raises(ValueError):
        evaluate_spec(PROFILE, bad, ai_model="x", day=DAY)
    spinach = int(FOODS[FOODS.name.str.contains("spinach", case=False)].fdc_id.iloc[0])
    bad = _spec(ok)
    bad["meals"][0]["items"].append({"fdc_id": spinach, "servings": 1})
    with pytest.raises(ValueError):
        evaluate_spec(PROFILE, bad, ai_model="x", day=DAY)


def test_diet_plan_endpoint_ai_and_fallback(monkeypatch):
    from fastapi.testclient import TestClient

    from api import llm
    from api.main import app
    ok, _, _ = allowed_pool(PROFILE)

    def fake_ok(system, user, validate, max_tokens=0):
        return {"data": validate(_spec(ok)), "model_used": "fake-llm", "failures": []}

    def fake_fail(*a, **k):
        raise llm.LlmError("offline")

    body = {"user_context": PROFILE, "severity_class": "Mild", "anemic": True}
    with TestClient(app) as c:
        monkeypatch.setattr(llm, "chat_json", fake_ok)
        r = c.post("/diet/plan", json=body).json()
        assert r["generated_by"] == "ai" and r["ai_model"] == "fake-llm" and r["meals"][0]["dish"] == "Rajma rice"
        assert r["goal"] and r["when_to_see_clinician"]
        monkeypatch.setattr(llm, "chat_json", fake_fail)
        r = c.post("/diet/plan", json=body).json()
        assert r["generated_by"] == "rules" and any("AI planner unavailable" in w for w in r["warnings"])
        assert len(c.get("/diet/foods").json()) == len(FOODS)
