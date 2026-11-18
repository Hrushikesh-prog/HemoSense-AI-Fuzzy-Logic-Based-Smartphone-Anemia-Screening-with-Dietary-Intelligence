"""WHO haemoglobin cut-offs -> anemia labels. Values live in clinical_config.json."""

from __future__ import annotations

import json
import os
from functools import lru_cache

_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clinical_config.json")


@lru_cache(maxsize=1)
def _cfg() -> dict:
    with open(_CFG_PATH, encoding="utf-8") as f:
        return json.load(f)


def group_for(sex: str | None, age_years: float | None = None, pregnant: bool = False) -> str:
    """Pick the WHO group. Unknown sex falls back to the stricter-for-screening 'woman' cut-off."""
    if age_years is not None and age_years < 5:
        return "child_6_59m"
    if pregnant:
        return "pregnant"
    s = (sex or "").strip().upper()[:1]
    return "man" if s == "M" else "woman"


def who_grade(hb: float, group: str) -> str:
    """Return 'Normal' | 'Mild' | 'Moderate' | 'Severe'."""
    g = _cfg()["groups"][group]
    if hb >= g["normal_min"]:
        return "Normal"
    if hb >= g["mild_min"]:
        return "Mild"
    if hb >= g["moderate_min"]:
        return "Moderate"
    return "Severe"


def is_anemic(hb: float, group: str) -> bool:
    return who_grade(hb, group) != "Normal"


def app_grade(who: str) -> str:
    """Collapse WHO grades to the three grades the app shows."""
    return {"Normal": "Normal", "Mild": "Mild"}.get(who, "Moderate-to-Severe")
