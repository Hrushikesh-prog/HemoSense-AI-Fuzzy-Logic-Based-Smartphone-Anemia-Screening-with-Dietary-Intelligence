"""Build the diet engine's food table from USDA FoodData Central (SR Legacy, 2018-04, public domain).

The only hand-made input is the CATALOGUE below: WHICH foods to offer (common in Indian diets and
relevant to iron), how they are labelled, which diets/meals they fit, and which household measure
is one serving. Every nutrient value (iron, vitamin C, calcium, protein, energy per 100 g) and every
serving weight in grams is read from the USDA files, with the FDC id kept for traceability.

Input:  research/data/usda/raw/FoodData_Central_sr_legacy_food_csv_2018-04/  (download:
        https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip)
Run:    python -I research/build_food_table.py
Out:    hemosense/data/foods_usda.csv (shipped with the server)
"""

from __future__ import annotations

import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "research", "data", "usda", "raw", "FoodData_Central_sr_legacy_food_csv_2018-04")
OUT = os.path.join(ROOT, "hemosense", "data", "foods_usda.csv")

NUTRIENTS = {1089: "iron_mg", 1162: "vitamin_c_mg", 1087: "calcium_mg", 1003: "protein_g", 1008: "energy_kcal"}

# name, exact USDA description, group, diets (V=vegan, L=lacto-veg, E=eggetarian, O=omnivore),
# heme iron?, phytate-rich?, serving (USDA measure keyword, amount), meals, allergens
# groups: legume, greens, grain, fruit_c (vitamin C source), dried_fruit, nuts_seeds, egg, meat, fish,
#         dairy (calcium: inhibitor), beverage_inhib (tea/coffee: inhibitor), veg_c
CATALOGUE = [
    ("Lentils (masoor-type dal), cooked", "Lentils, mature seeds, cooked, boiled, without salt", "legume", "VLEO", 0, 1, ("cup", 1), "LD", ""),
    ("Chana / chickpeas", "Chickpeas (garbanzo beans, bengal gram), mature seeds, cooked, boiled, without salt", "legume", "VLEO", 0, 1, ("cup", 1), "LD", ""),
    ("Rajma / kidney beans", "Beans, kidney, red, mature seeds, cooked, boiled, without salt", "legume", "VLEO", 0, 1, ("cup", 1), "LD", ""),
    ("Lobia / black-eyed peas", "Cowpeas, common (blackeyes, crowder, southern), mature seeds, cooked, boiled, without salt", "legume", "VLEO", 0, 1, ("cup", 1), "LD", ""),
    ("Sprouted moong", "Mung beans, mature seeds, sprouted, raw", "legume", "VLEO", 0, 0, ("cup", 1), "BS", ""),
    ("Tofu", "Tofu, raw, firm, prepared with calcium sulfate", "legume", "VLEO", 0, 1, ("cup", 0.5), "LD", "soy"),
    ("Green peas", "Peas, green, cooked, boiled, drained, without salt", "legume", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Palak / spinach (cooked)", "Spinach, cooked, boiled, drained, without salt", "greens", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Chaulai / amaranth leaves", "Amaranth leaves, cooked, boiled, drained, without salt", "greens", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Sarson / mustard greens", "Mustard greens, cooked, boiled, drained, without salt", "greens", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Moringa / drumstick leaves", "Drumstick leaves, cooked, boiled, drained, without salt", "greens", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Beet greens", "Beet greens, cooked, boiled, drained, without salt", "greens", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Millet, cooked (proso millet)", "Millet, cooked", "grain", "VLEO", 0, 1, ("cup", 1), "BLD", ""),
    ("Oats (dry, for porridge)", "Cereals, oats, regular and quick, not fortified, dry", "grain", "VLEO", 0, 1, ("cup", 0.5), "B", "gluten"),
    ("Quinoa (cooked)", "Quinoa, cooked", "grain", "VLEO", 0, 1, ("cup", 1), "LD", ""),
    ("Whole-wheat bread", "Bread, whole-wheat, commercially prepared", "grain", "VLEO", 0, 1, ("slice", 2), "BLD", "gluten"),
    ("Brown rice (cooked)", "Rice, brown, long-grain, cooked (Includes foods for USDA's Food Distribution Program)", "grain", "VLEO", 0, 1, ("cup", 1), "LD", ""),
    ("Jowar / sorghum flour", "Sorghum flour, whole-grain", "grain", "VLEO", 0, 1, ("cup", 0.25), "BLD", ""),
    ("Boiled egg", "Egg, whole, cooked, hard-boiled", "egg", "EO", 0, 0, ("large", 2), "BS", "egg"),
    ("Chicken liver", "Chicken, liver, all classes, cooked, simmered", "meat", "O", 1, 0, ("oz", 3), "LD", ""),
    ("Chicken breast", "Chicken, broilers or fryers, breast, meat only, cooked, roasted", "meat", "O", 1, 0, ("breast, bone", 1), "LD", ""),
    ("Goat meat (mutton)", "Game meat, goat, cooked, roasted", "meat", "O", 1, 0, ("oz", 3), "LD", ""),
    ("Sardines", "Fish, sardine, Atlantic, canned in oil, drained solids with bone", "fish", "O", 1, 0, ("oz", 3), "LD", "fish"),
    ("Atlantic mackerel", "Fish, mackerel, Atlantic, cooked, dry heat", "fish", "O", 1, 0, ("oz", 3), "LD", "fish"),
    ("Carp (common carp)", "Fish, carp, cooked, dry heat", "fish", "O", 1, 0, ("oz", 3), "LD", "fish"),
    ("Prawns / shrimp", "Crustaceans, shrimp, mixed species, cooked, moist heat (may contain additives to retain moisture)", "fish", "O", 1, 0, ("oz", 3), "LD", "shellfish"),
    ("Dates (khajur)", "Dates, medjool", "dried_fruit", "VLEO", 0, 0, ("date", 3), "S", ""),
    ("Dried figs (anjeer)", "Figs, dried, uncooked", "dried_fruit", "VLEO", 0, 0, ("fig", 3), "S", ""),
    ("Dried apricots", "Apricots, dried, sulfured, uncooked", "dried_fruit", "VLEO", 0, 0, ("half", 6), "S", ""),
    ("Pumpkin seeds", "Seeds, pumpkin and squash seed kernels, dried", "nuts_seeds", "VLEO", 0, 1, ("oz", 1), "S", ""),
    ("Til / sesame seeds", "Seeds, sesame seeds, whole, dried", "nuts_seeds", "VLEO", 0, 1, ("tbsp", 2), "S", "sesame"),
    ("Peanuts (roasted)", "Peanuts, all types, dry-roasted, without salt", "nuts_seeds", "VLEO", 0, 1, ("oz", 1), "S", "peanut"),
    ("Cashews (roasted)", "Nuts, cashew nuts, dry roasted, without salt added", "nuts_seeds", "VLEO", 0, 1, ("oz", 1), "S", "tree nut"),
    ("Guava", "Guavas, common, raw", "fruit_c", "VLEO", 0, 0, ("fruit", 1), "BLSD", ""),
    ("Orange", "Oranges, raw, all commercial varieties", "fruit_c", "VLEO", 0, 0, ("fruit", 1), "BLSD", ""),
    ("Papaya", "Papayas, raw", "fruit_c", "VLEO", 0, 0, ("cup", 1), "BLSD", ""),
    ("Kiwi", "Kiwifruit, green, raw", "fruit_c", "VLEO", 0, 0, ("fruit", 1), "BLSD", ""),
    ("Lemon juice (squeezed over food)", "Lemon juice, raw", "fruit_c", "VLEO", 0, 0, ("lemon yields", 1), "LD", ""),
    ("Tomato (raw, salad)", "Tomatoes, red, ripe, raw, year round average", "veg_c", "VLEO", 0, 0, ("medium", 1), "LD", ""),
    ("Red capsicum", "Peppers, sweet, red, raw", "veg_c", "VLEO", 0, 0, ("cup", 0.5), "LD", ""),
    ("Cauliflower (cooked)", "Cauliflower, cooked, boiled, drained, without salt", "veg_c", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Broccoli (cooked)", "Broccoli, cooked, boiled, drained, without salt", "veg_c", "VLEO", 0, 0, ("cup", 1), "LD", ""),
    ("Milk", "Milk, whole, 3.25% milkfat, with added vitamin D", "dairy", "LEO", 0, 0, ("cup", 1), "BS", "milk"),
    ("Curd / plain yogurt", "Yogurt, plain, whole milk", "dairy", "LEO", 0, 0, ("cup", 1), "LD", "milk"),
    ("Black tea", "Beverages, tea, black, brewed, prepared with tap water", "beverage_inhib", "VLEO", 0, 0, ("fl oz", 8), "BS", ""),
    ("Coffee", "Beverages, coffee, brewed, prepared with tap water", "beverage_inhib", "VLEO", 0, 0, ("fl oz", 8), "BS", ""),
]
COLUMNS = ["name", "usda_description", "group", "diets", "heme", "phytate_rich", "serving_measure",
           "serving_amount", "meals", "allergens"]


def main() -> None:
    food = pd.read_csv(os.path.join(SRC, "food.csv"), usecols=["fdc_id", "description"])
    fn = pd.read_csv(os.path.join(SRC, "food_nutrient.csv"), usecols=["fdc_id", "nutrient_id", "amount"])
    portion = pd.read_csv(os.path.join(SRC, "food_portion.csv"),
                          usecols=["fdc_id", "amount", "modifier", "gram_weight"])
    cat = pd.DataFrame([dict(zip(COLUMNS, (*c[:6], c[6][0], c[6][1], *c[7:]))) for c in CATALOGUE])
    rows, problems = [], []
    for c in cat.itertuples():
        hit = food[food.description == c.usda_description]
        if hit.empty:
            problems.append(f"not found: {c.usda_description}")
            continue
        fid = int(hit.fdc_id.iloc[0])
        n = fn[(fn.fdc_id == fid) & fn.nutrient_id.isin(NUTRIENTS)].set_index("nutrient_id").amount
        p = portion[(portion.fdc_id == fid)
                    & portion.modifier.fillna("").str.lower().str.contains(c.serving_measure, regex=False)]
        if p.empty:
            problems.append(f"no '{c.serving_measure}' portion for {c.name} (fdc {fid})")
            continue
        p = p.iloc[0]
        grams = float(p.gram_weight) / float(p.amount or 1) * c.serving_amount
        rec = c._asdict()
        rec.pop("Index")
        rec.update({"fdc_id": fid, "serving_grams": round(grams, 1),
                    "serving_label": f"{c.serving_amount:g} x {p.modifier}"})
        rec.update({col: float(n.get(nid, 0.0)) for nid, col in NUTRIENTS.items()})
        rows.append(rec)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"{len(rows)} foods -> {OUT}")
    for pr in problems:
        print("  PROBLEM:", pr)


if __name__ == "__main__":
    main()
