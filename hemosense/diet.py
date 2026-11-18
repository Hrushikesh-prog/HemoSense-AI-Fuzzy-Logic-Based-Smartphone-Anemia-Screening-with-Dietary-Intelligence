"""Absorption-aware daily iron meal plan from real food-composition data.

Data:   hemosense/data/foods_usda.csv  (USDA FoodData Central SR Legacy; built by
        research/build_food_table.py; every nutrient value and serving weight is USDA's).
Config: hemosense/diet_config.json     (RDA targets and absorption factors, each with a source).

Model per meal (project design):
  absorbable = heme_Fe * 0.25 + nonheme_Fe * 0.10 * E * I
  E = 2   if the meal has >= 25 mg vitamin C or contains meat/fish (enhancers)
  I = 0.7 if the meal has >= 300 mg calcium; x0.8 if phytate-rich foods carry most of the
      non-heme iron and no enhancer is present.

Two planners share the same data and the same evaluation:
  * build_plan()    rules: greedy, picks the food that adds the most absorbable iron per slot.
  * evaluate_spec() checks and scores a plan proposed by the AI planner: only foods from
    allowed_pool() are accepted and every nutrient number is recomputed here.
Questionnaire (user_context.diet_profile): dislikes (removed, with a data-based replacement),
skips_breakfast, night_shift, kitchen, fridge (no fridge -> no fresh meat/fish), budget/state (AI).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from functools import lru_cache

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_SOURCE = "USDA FoodData Central, SR Legacy 2018-04 (public domain); FDC id given per food"
MEAL_TIMES = {"Breakfast": "8:00 am", "Lunch": "1:00 pm", "Snack": "4:30 pm", "Dinner": "8:00 pm"}
NIGHT_TIMES = {"Breakfast": "6:00 pm", "Lunch": "11:30 pm", "Snack": "3:00 am", "Dinner": "8:00 am"}


@lru_cache(maxsize=1)
def _foods() -> pd.DataFrame:
    return pd.read_csv(os.path.join(_HERE, "data", "foods_usda.csv")).rename(columns={"name": "food_name"})


@lru_cache(maxsize=1)
def _cfg() -> dict:
    with open(os.path.join(_HERE, "diet_config.json"), encoding="utf-8") as f:
        return json.load(f)


def food_catalogue() -> list[dict]:
    """Public list for the app's dislike picker."""
    return [{"fdc_id": int(r.fdc_id), "name": r.food_name, "group": r.group} for r in _foods().itertuples()]


def _diet_code(diet: str | None) -> str:
    d = (diet or "").strip().lower()
    if d in ("vegan", "plant-based", "plant based"):
        return "V"
    if d in ("eggetarian", "ovo-vegetarian"):
        return "E"
    if d in ("vegetarian", "veg", "lacto-vegetarian", "jain"):
        return "L"
    return "O"


def _profile(ctx: dict) -> dict:
    return ctx.get("diet_profile") or {}


def iron_target(ctx: dict) -> tuple[float, str]:
    rda = _cfg()["iron_rda_mg"]
    age = ctx.get("age")
    female = (ctx.get("sex") or "").lower().startswith("f")
    if ctx.get("pregnant"):
        return rda["pregnant"], "RDA, pregnancy (NIH ODS)"
    if age is not None and age < 19:
        k = "adolescent_female_14_18" if female else "adolescent_male_14_18"
        return rda[k], f"RDA, {'girls' if female else 'boys'} 14-18 (NIH ODS)"
    if female:
        if age is not None and age >= 51:
            return rda["female_51_plus"], "RDA, women 51+ (NIH ODS)"
        return rda["female_19_50"], "RDA, women 19-50 (NIH ODS)"
    return rda["male_19_plus"], "RDA, men 19+ (NIH ODS)"


def _serving(row, servings: float = 1.0) -> dict:
    g = float(row.serving_grams) * servings
    k = g / 100.0
    return {"food": row.food_name, "grams": round(g), "servings": servings,
            "serving": row.serving_label if servings == 1 else f"{servings:g} x ({row.serving_label})",
            "iron_mg": round(row.iron_mg * k, 2), "vitamin_c_mg": round(row.vitamin_c_mg * k, 1),
            "calcium_mg": round(row.calcium_mg * k), "heme": bool(row.heme),
            "phytate_rich": bool(row.phytate_rich), "group": row.group, "fdc_id": int(row.fdc_id)}


def meal_absorption(items: list[dict]) -> tuple[float, float, list[str]]:
    a = _cfg()["absorption"]
    heme = sum(i["iron_mg"] for i in items if i["heme"])
    nonheme = sum(i["iron_mg"] for i in items if not i["heme"])
    vit_c = sum(i["vitamin_c_mg"] for i in items)
    calcium = sum(i["calcium_mg"] for i in items)
    has_mf = any(i["group"] in ("meat", "fish") for i in items)
    reasons = []
    e = 1.0
    if vit_c >= a["enhancer_min_vitamin_c_mg"] or has_mf:
        e = a["enhancer_multiplier"]
        reasons.append(f"{vit_c:.0f} mg vitamin C" + (" and meat/fish" if has_mf else "")
                       + " roughly doubles plant-iron absorption")
    i_mult = 1.0
    if calcium >= a["calcium_inhibition_min_mg"]:
        i_mult *= a["calcium_inhibition_multiplier"]
        reasons.append(f"{calcium:.0f} mg calcium in this meal lowers absorption")
    phy = sum(i["iron_mg"] for i in items if not i["heme"] and i["phytate_rich"])
    if e == 1.0 and nonheme > 0 and phy / nonheme > 0.5:
        i_mult *= a["phytate_multiplier"]
        reasons.append("phytate-rich grains/legumes without vitamin C lower absorption")
    absorbable = heme * a["heme"] + nonheme * a["non_heme"] * e * i_mult
    return heme + nonheme, absorbable, reasons


def _matches(food_name: str, text: str) -> bool:
    f, t = food_name.lower(), text.strip().lower()
    return bool(t) and (t in f or any(w in f for w in t.replace("/", " ").split() if len(w) > 3))


def allowed_pool(ctx: dict) -> tuple[pd.DataFrame, list[dict], list[str]]:
    """Foods this person can be offered, the replacement for each dislike, and warnings."""
    prof = _profile(ctx)
    diet = _diet_code(ctx.get("diet"))
    foods = _foods()
    ok = foods[foods.diets.str.contains(diet)]
    allergies = [a.strip().lower() for a in (ctx.get("allergies") or []) if a and a.strip()]
    if allergies:
        ok = ok[~ok.apply(lambda r: any(a in str(r.allergens).lower() or a in r.food_name.lower()
                                        for a in allergies), axis=1)]
    if ctx.get("pregnant"):
        ok = ok[~ok.food_name.isin(_cfg()["exclude_in_pregnancy"]["foods"])]
    warnings = []
    if prof.get("fridge") is False and diet == "O":
        ok = ok[~ok.group.isin(["meat", "fish"])]
        warnings.append("No fridge: fresh meat and fish are left out; eggs, legumes and greens cover iron instead.")

    dislikes = [d for d in (prof.get("dislikes") or []) if d and d.strip()]
    hits = {d: ok[ok.food_name.apply(lambda n, d=d: _matches(n, d))] for d in dislikes}
    disliked_ids = {int(x) for h in hits.values() for x in h.fdc_id}
    replacements = []
    for d, hit in hits.items():
        if hit.empty:
            replacements.append({"disliked": d, "replacement": None,
                                 "reason": "Not in our food list, so it is simply never suggested."})
            continue
        src = hit.iloc[0]
        s_src = _serving(src)
        cand = ok[(ok.group == src.group) & ~ok.fdc_id.isin(disliked_ids)]
        if cand.empty:
            replacements.append({"disliked": src.food_name, "replacement": None,
                                 "reason": "No other food of the same kind is available for your diet."})
            continue
        dist = cand.apply(lambda r: abs(_serving(r)["iron_mg"] - s_src["iron_mg"])
                          + 0.02 * abs(_serving(r)["vitamin_c_mg"] - s_src["vitamin_c_mg"]), axis=1)
        rep = cand.loc[dist.idxmin()]
        s_rep = _serving(rep)
        replacements.append({
            "disliked": src.food_name, "replacement": rep.food_name,
            "reason": (f"Same food group; {s_rep['iron_mg']:g} mg iron and {s_rep['vitamin_c_mg']:g} mg vitamin C "
                       f"per {rep.serving_label}, vs {s_src['iron_mg']:g} mg and {s_src['vitamin_c_mg']:g} mg "
                       f"per {src.serving_label} of {src.food_name} (USDA).")})
    ok = ok[~ok.fdc_id.isin(disliked_ids)]
    return ok, replacements, warnings


def _meal_names(ctx: dict) -> list[str]:
    names = list(_cfg()["meal_slots"])
    if _profile(ctx).get("skips_breakfast"):
        names = [m for m in names if m != "Breakfast"]
    return names


def _times(ctx: dict) -> dict:
    return NIGHT_TIMES if _profile(ctx).get("night_shift") else MEAL_TIMES


def _seed(ctx: dict, day: _dt.date) -> int:
    key = f"{day.isoformat()}|{ctx.get('sex')}|{ctx.get('age')}|{ctx.get('diet')}|{sorted(ctx.get('allergies') or [])}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def _finish(ctx: dict, meals: list[dict], ok: pd.DataFrame, extra: dict) -> dict:
    """Shared output: per-meal and daily totals from the data, plus inhibitor advice."""
    diet = _diet_code(ctx.get("diet"))
    target, basis = iron_target(ctx)
    tot_iron = tot_abs = 0.0
    for m in meals:
        iron, absorbable, reasons = meal_absorption(m["items"])
        m.update(iron_mg=round(iron, 1), absorbable_iron_mg=round(absorbable, 2),
                 note="; ".join(reasons))
        tot_iron += iron
        tot_abs += absorbable
    bio = _cfg()["typical_bioavailability"]["omnivore" if diet == "O" else "vegetarian"]
    a = _cfg()["absorption"]
    foods = _foods()
    inhib = foods[foods.group.isin(["beverage_inhib", "dairy"]) & foods.diets.str.contains(diet)]
    avoid = []
    for r in inhib.itertuples():
        s = _serving(r)
        if r.group == "beverage_inhib":
            avoid.append(f"{r.food_name} with meals: can cut iron absorption to about "
                         f"{a['tea_coffee_multiplier']:.0%}; keep it 1 hour away from iron-rich meals")
        else:
            avoid.append(f"{r.food_name} at iron-rich meals: {s['calcium_mg']} mg calcium per {s['serving']} "
                         f"(USDA); have it between meals")
    pool = ok[~ok.group.isin(["dairy", "beverage_inhib"])]
    by_iron = pool.assign(per=pool.iron_mg * pool.serving_grams / 100).sort_values("per", ascending=False)
    by_c = ok[ok.group.isin(["fruit_c", "veg_c"])].assign(
        per=ok.vitamin_c_mg * ok.serving_grams / 100).sort_values("per", ascending=False)
    warnings = list(extra.pop("warnings", []))
    if tot_iron < target:
        warnings.append(f"This plan gives {tot_iron:.1f} mg iron, below the {target:g} mg target.")
    daily_extra = extra.pop("daily_extra", {})
    return {
        "diet_type": {"V": "vegan", "L": "vegetarian", "E": "eggetarian", "O": "omnivore"}[diet],
        "meals": meals,
        "daily": {"iron_mg": round(tot_iron, 1), "absorbable_iron_mg": round(tot_abs, 2),
                  "target_iron_mg": float(target), "target_basis": basis,
                  "absorbed_target_mg": round(target * bio, 2), **daily_extra},
        "iron_rich_foods": [f"{r.food_name}: {r.per:.1f} mg iron per {r.serving_label}" for r in by_iron.head(6).itertuples()],
        "pair_with_vitamin_c": [f"{r.food_name}: {r.per:.0f} mg vitamin C per {r.serving_label}" for r in by_c.head(4).itertuples()],
        "avoid_or_limit": avoid,
        "sample_day": {m["meal"]: (m.get("dish") or ", ".join(i["food"] for i in m["items"])) for m in meals},
        "data_source": DATA_SOURCE,
        "warnings": warnings,
        **extra,
    }


def build_plan(ctx: dict | None, severity: str, day: _dt.date | None = None) -> dict:
    """Rule-based planner (also the fallback when the AI planner is unavailable)."""
    ctx = ctx or {}
    day = day or _dt.date.today()
    rng = np.random.default_rng(_seed(ctx, day))
    ok, replacements, warnings = allowed_pool(ctx)
    pool = ok[~ok.group.isin(["dairy", "beverage_inhib"])]
    used: set[int] = set()
    times = _times(ctx)
    meals = []
    for meal in _meal_names(ctx):
        code = meal[0]
        items: list[dict] = []
        for slot in _cfg()["meal_slots"][meal]:
            cand = pool[pool.group.isin(slot.split("|")) & pool.meals.str.contains(code) & ~pool.fdc_id.isin(used)]
            if cand.empty:
                continue
            base = meal_absorption(items)[1]
            gains = np.array([meal_absorption(items + [_serving(r)])[1] - base + 0.002 * _serving(r)["vitamin_c_mg"]
                              for r in cand.itertuples()])
            gains = gains * rng.uniform(0.75, 1.25, len(gains))      # day-to-day variety
            pick = cand.iloc[int(np.argmax(gains))]
            items.append(_serving(pick))
            used.add(int(pick.fdc_id))
        meals.append({"meal": meal, "time": times[meal], "dish": None, "est_cost_inr": None, "items": items})

    target, _ = iron_target(ctx)
    for _ in range(4):        # top up until the RDA is met
        if sum(meal_absorption(m["items"])[0] for m in meals) >= target:
            break
        cand = pool[~pool.fdc_id.isin(used) & pool.group.isin(
            ["legume", "greens", "nuts_seeds", "dried_fruit", "meat", "fish", "egg"])]
        best = None
        for r in cand.itertuples():
            s = _serving(r)
            for m in meals:
                if m["meal"][0] not in r.meals:
                    continue
                gain = meal_absorption(m["items"] + [s])[1] - meal_absorption(m["items"])[1]
                if best is None or gain > best[0]:
                    best = (gain, m, s)
        if best is None:
            break
        best[1]["items"].append(best[2])
        used.add(best[2]["fdc_id"])
    if _profile(ctx).get("kitchen") == "none":
        warnings.append("No kitchen: ask for these items at your canteen or mess (dal, rajma, chana, greens, "
                        "eggs) and carry fruit, seeds or dried fruit for snacks.")
    return _finish(ctx, meals, ok, {"replacements": replacements, "warnings": warnings,
                                    "generated_by": "rules", "ai_model": None, "cost_basis": None,
                                    "plan_date": day.isoformat()})


def evaluate_spec(ctx: dict, spec: dict, ai_model: str, day: _dt.date | None = None) -> dict:
    """Validate an AI-proposed plan against allowed_pool() and recompute every number from data.
    Raises ValueError if the proposal uses a food outside the allowed list or is malformed."""
    day = day or _dt.date.today()
    ok, replacements, warnings = allowed_pool(ctx)
    allowed = {int(r.fdc_id): r for r in ok.itertuples()}
    wanted = set(_meal_names(ctx))
    meals = []
    for m in spec.get("meals") or []:
        name = str(m.get("meal", "")).strip().title()
        if name not in wanted:
            continue
        items = []
        for it in m.get("items") or []:
            fid = int(it["fdc_id"])
            if fid not in allowed:
                raise ValueError(f"food {fid} is not allowed for this person")
            if allowed[fid].group in ("dairy", "beverage_inhib"):
                raise ValueError(f"food {fid} inhibits iron absorption and cannot be in a meal")
            sv = float(it.get("servings", 1))
            if not 0.25 <= sv <= 3:
                raise ValueError(f"servings {sv} out of range")
            items.append(_serving(allowed[fid], sv))
        if not items:
            raise ValueError(f"meal {name} has no valid foods")
        cost = m.get("est_cost_inr")
        meals.append({"meal": name, "time": str(m.get("time") or _times(ctx)[name])[:20],
                      "dish": str(m.get("dish") or "")[:80] or None,
                      "est_cost_inr": round(float(cost)) if isinstance(cost, (int, float)) and cost >= 0 else None,
                      "items": items})
    if len(meals) < max(2, len(wanted) - 1):
        raise ValueError("too few meals")
    order = list(_cfg()["meal_slots"])
    meals.sort(key=lambda m: order.index(m["meal"]))
    prof = _profile(ctx)
    costs = [m["est_cost_inr"] for m in meals if m["est_cost_inr"] is not None]
    est_total = round(sum(costs)) if costs and len(costs) == len(meals) else None
    budget = prof.get("budget_inr_per_day")
    if est_total is not None and budget and est_total > budget:
        warnings.append(f"AI-estimated cost (about Rs {est_total}) is above your budget of Rs {budget:g}.")
    for note in (spec.get("tips") or [])[:4]:
        if isinstance(note, str) and note.strip():
            warnings.append(note.strip()[:200])
    place = ", ".join(x for x in (prof.get("city"), prof.get("state")) if x) or "your area"
    area = prof.get("area_type") or ""
    return _finish(ctx, meals, ok, {
        "replacements": replacements, "warnings": warnings, "generated_by": "ai", "ai_model": ai_model,
        "cost_basis": (f"AI estimate of local retail prices for {place}{' (' + area + ')' if area else ''}, "
                       f"{day.strftime('%b %Y')}; not official prices") if est_total is not None else None,
        "daily_extra": {"est_cost_inr": est_total, "budget_inr": budget},
        "plan_date": day.isoformat()})


def ai_brief(ctx: dict, severity: str) -> tuple[str, str]:
    """System + user prompt for the AI planner: the allowed foods (ids + USDA numbers) and the person."""
    ok, replacements, _ = allowed_pool(ctx)
    pool = ok[~ok.group.isin(["dairy", "beverage_inhib"])]
    lines = []
    for r in pool.itertuples():
        s = _serving(r)
        lines.append(f"{s['fdc_id']} | {r.food_name} | {r.group} | 1 serving = {r.serving_label} = {s['grams']} g | "
                     f"iron {s['iron_mg']} mg | vitamin C {s['vitamin_c_mg']} mg | {'heme' if r.heme else 'plant'} | meals {r.meals}")
    target, basis = iron_target(ctx)
    prof = _profile(ctx)
    system = (
        "You are a dietitian planning one day of iron-focused meals for a person in India. "
        "You may ONLY use foods from the provided list, referenced by their fdc_id, with 0.5 to 2 servings each. "
        "Every iron meal must include a vitamin C food from the list. Never include tea, coffee, milk or curd in meals. "
        "Give each meal a realistic local dish name for the person's state that combines the chosen foods, a time, "
        "and an estimated cost in Indian rupees for buying those ingredients in their area today (your best estimate). "
        "Respect budget, kitchen access and routine. Reply with ONE JSON object only, no prose, in this shape: "
        '{"meals":[{"meal":"Breakfast|Lunch|Snack|Dinner","time":"8:00 am","dish":"...",'
        '"est_cost_inr":40,"items":[{"fdc_id":123,"servings":1}]}],"tips":["..."]}'
    )
    user = json.dumps({
        "severity": severity, "daily_iron_target_mg": target, "target_basis": basis,
        "diet": ctx.get("diet"), "sex": ctx.get("sex"), "age": ctx.get("age"), "pregnant": ctx.get("pregnant"),
        "budget_inr_per_day": prof.get("budget_inr_per_day"), "state": prof.get("state"), "city": prof.get("city"),
        "area_type": prof.get("area_type"), "kitchen": prof.get("kitchen"), "fridge": prof.get("fridge"),
        "meals_wanted": _meal_names(ctx), "night_shift": prof.get("night_shift"),
        "replacements_already_applied": [r for r in replacements if r.get("replacement")],
    }, ensure_ascii=False) + "\n\nAllowed foods (fdc_id | name | group | serving | iron | vitamin C | type | meals B/L/S/D):\n" + "\n".join(lines)
    return system, user
