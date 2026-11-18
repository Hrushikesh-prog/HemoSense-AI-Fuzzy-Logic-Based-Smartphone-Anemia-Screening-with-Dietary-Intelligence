"""Eyes-defy-anemia loader: one row per participant (no image-level leakage).

Folder layout: <root>/<India|Italy>/<Number>/{photo.jpg, *_palpebral.png, ...}
with <root>/<Region>/<Region>.xlsx holding Number, Hgb, Gender, Age.
"""

from __future__ import annotations

import glob
import os

import pandas as pd

from hemosense.labels import group_for, is_anemic, who_grade

DEFAULT_ROOT = os.environ.get(
    "HEMOSENSE_DATA_ROOT",
    r"C:\Users\pushp\Downloads\CapstoneProject (4)\CapstoneProject\dataset\datasetanemia",
)
REGIONS = ("India", "Italy")


def _to_float(x) -> float | None:
    """Parse Hb values; the Italy sheet uses decimal commas ('15,1')."""
    try:
        return float(str(x).strip().replace(",", "."))
    except ValueError:
        return None


def _find(folder: str, kind: str) -> str | None:
    if kind == "photo":
        hits = [p for p in glob.glob(os.path.join(folder, "*"))
                if p.lower().endswith((".jpg", ".jpeg"))]
        return sorted(hits)[0] if hits else None
    hits = [p for p in glob.glob(os.path.join(folder, "*.png"))
            if os.path.basename(p).lower().endswith(f"_{kind}.png")
            and (kind != "palpebral" or "forniceal" not in os.path.basename(p).lower())]
    return sorted(hits)[0] if hits else None


def load_participants(root: str = DEFAULT_ROOT) -> tuple[pd.DataFrame, list[dict]]:
    """Return (participants dataframe, list of exclusions with reasons)."""
    rows, excluded = [], []
    for region in REGIONS:
        meta = pd.read_excel(os.path.join(root, region, f"{region}.xlsx"))
        for _, r in meta.iterrows():
            pid = f"{region}-{int(r['Number'])}"
            folder = os.path.join(root, region, str(int(r["Number"])))
            hb = _to_float(r["Hgb"])
            if hb is None:
                excluded.append({"pid": pid, "reason": "Hb not available"})
                continue
            palp = _find(folder, "palpebral")
            if palp is None:
                excluded.append({"pid": pid, "reason": "no palpebral mask"})
                continue
            sex = str(r["Gender"]).strip().upper()[:1]
            age = _to_float(r["Age"])
            group = group_for(sex, age)
            grade = who_grade(hb, group)
            rows.append({
                "pid": pid, "region": region, "number": int(r["Number"]),
                "hb": hb, "sex": sex, "age": age, "group": group,
                "who_grade": grade, "anemic": int(is_anemic(hb, group)),
                "mod_sev": int(grade in ("Moderate", "Severe")),
                "palpebral_png": palp, "photo": _find(folder, "photo"),
            })
    return pd.DataFrame(rows), excluded
