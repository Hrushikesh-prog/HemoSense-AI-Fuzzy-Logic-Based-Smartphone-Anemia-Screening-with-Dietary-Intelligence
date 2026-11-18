"""Step 1: per-participant colour features for every pipeline variant.

Variants (used for the ablations):
  mask_raw     expert palpebral mask, raw colours                (main setting)
  mask_fuzzy   expert mask after the fuzzy illumination correction (Phase 2)
  auto_raw     automatic Haar ROI from the full photo (what the API does), raw colours
  auto_fuzzy   automatic ROI + fuzzy correction

Also writes 224x224 masked crops (research/data/crops/<pid>.png) for the CNN baseline.

Run:  python -m research.extract_features
Out:  research/results/features.csv, research/results/exclusions.json
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time

import cv2
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scratch"))

from hemosense.data import load_participants  # noqa: E402
from hemosense.features import extract_features, mask_from_rgba, to_float_rgb  # noqa: E402

RESULTS = os.path.join(ROOT, "research", "results")
CROPS = os.path.join(ROOT, "research", "data", "crops")


def _to_u8_bgr(img: np.ndarray) -> np.ndarray:
    if img.dtype == np.uint16:
        img = (img / 257.0).astype(np.uint8)
    return np.ascontiguousarray(img[..., :3])


def _quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


def _crop_to_mask(bgr: np.ndarray, mask: np.ndarray, size: int = 224) -> np.ndarray:
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    c = bgr[y0:y1, x0:x1].copy()
    c[~mask[y0:y1, x0:x1]] = 0
    h, w = c.shape[:2]
    s = max(h, w)
    sq = np.zeros((s, s, 3), np.uint8)
    sq[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = c
    return cv2.resize(sq, (size, size), interpolation=cv2.INTER_AREA)


def main() -> None:
    from anemia_pipeline import apply_fuzzy_correction, extract_conjunctiva_roi

    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(CROPS, exist_ok=True)
    df, excluded = load_participants()
    print(f"{len(df)} participants, {len(excluded)} excluded: {excluded}")

    out = []
    t0 = time.time()
    for i, row in df.iterrows():
        rec = {k: row[k] for k in ("pid", "region", "hb", "sex", "age", "group",
                                   "who_grade", "anemic", "mod_sev")}
        png = cv2.imread(row["palpebral_png"], cv2.IMREAD_UNCHANGED)
        mask = mask_from_rgba(png)
        bgr8 = _to_u8_bgr(png)
        try:
            for name, img in (("mask_raw", bgr8), ("mask_fuzzy", _quiet(apply_fuzzy_correction, bgr8))):
                f = extract_features(to_float_rgb(img), mask)
                rec.update({f"{name}__{k}": v for k, v in f.items()})
            cv2.imwrite(os.path.join(CROPS, f"{row['pid']}.png"), _crop_to_mask(bgr8, mask))
        except ValueError as exc:
            excluded.append({"pid": row["pid"], "reason": f"mask features failed: {exc}"})
            continue

        photo = cv2.imread(row["photo"]) if isinstance(row["photo"], str) else None
        if photo is not None:
            roi = _quiet(extract_conjunctiva_roi, photo)
            for name, img in (("auto_raw", roi), ("auto_fuzzy", _quiet(apply_fuzzy_correction, roi))):
                try:
                    f = extract_features(to_float_rgb(img))
                    rec.update({f"{name}__{k}": v for k, v in f.items()})
                except ValueError:
                    pass
        out.append(rec)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(df)}  ({time.time() - t0:.0f}s)", flush=True)

    feats = pd.DataFrame(out)
    feats.to_csv(os.path.join(RESULTS, "features.csv"), index=False)
    with open(os.path.join(RESULTS, "exclusions.json"), "w", encoding="utf-8") as f:
        json.dump(excluded, f, indent=2)
    print(f"saved {len(feats)} rows -> research/results/features.csv in {time.time() - t0:.0f}s")
    print(feats.groupby("region")[["anemic", "mod_sev"]].agg(["sum", "count"]))


if __name__ == "__main__":
    main()
