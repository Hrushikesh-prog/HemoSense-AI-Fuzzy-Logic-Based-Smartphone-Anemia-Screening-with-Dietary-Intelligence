"""Simulate the live app path on the dataset photos.

For each participant a box is placed around the expert conjunctiva mask, expanded by
a random 10-40 % margin and jittered (as a user would draw it). The serving segmenter
(hemosense.segment) then runs on the photo at serving resolution. We record:
  - quality-gate outcome and Dice / precision / recall vs the expert forniceal+palpebral mask
  - colour features on the automatic mask         -> columns live_sim__*
  - colour features on the expert union mask      -> columns union__*  (reference)

Needs:  python -m research.cache_photos   (once)
Run:    python -m research.live_path_sim
Out:    research/results/live_sim_features.csv, research/results/live_sim_summary.json
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hemosense.data import load_participants  # noqa: E402
from hemosense.colour import apply_gains, estimate_white_balance  # noqa: E402
from hemosense.features import extract_features, to_float_rgb  # noqa: E402
from hemosense.segment import clamp_box  # noqa: E402
from hemosense.segment import segment_conjunctiva  # noqa: E402

RESULTS = os.path.join(ROOT, "research", "results")
CACHE = os.path.join(ROOT, "research", "data", "cache")


def sim_box(mask: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float, float]:
    H, W = mask.shape
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min() / W, (xs.max() + 1) / W, ys.min() / H, (ys.max() + 1) / H
    bw, bh = x1 - x0, y1 - y0
    m = rng.uniform(0.10, 0.40)
    jx, jy = rng.uniform(-0.1, 0.1) * bw, rng.uniform(-0.1, 0.1) * bh
    nx0, ny0 = max(x0 - m * bw + jx, 0.0), max(y0 - m * bh + jy, 0.0)
    nw, nh = bw * (1 + 2 * m), bh * (1 + 2 * m)
    return nx0, ny0, min(nw, 1 - nx0), min(nh, 1 - ny0)


def main(seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    df, _ = load_participants()
    rows = []
    for i, r in enumerate(df.itertuples()):
        path = os.path.join(CACHE, f"{r.pid}.npz")
        rec = {"pid": r.pid, "region": r.region, "anemic": r.anemic, "mod_sev": r.mod_sev, "hb": r.hb}
        if not os.path.exists(path):
            rec["status"] = "no_photo"
            rows.append(rec)
            continue
        d = np.load(path)
        img, gt = d["img"], d["union"]
        rec.update({f"union__{k}": v for k, v in extract_features(to_float_rgb(img), gt).items()})
        box = sim_box(gt, rng)
        rec["box"] = json.dumps([round(b, 4) for b in box])
        res = segment_conjunctiva(img, box)
        rec.update({f"q_{k}": v for k, v in (res.quality or {}).items()})
        rec["status"] = "ok" if res.ok else res.code
        if res.ok:
            inter = (gt & res.mask).sum()
            rec["dice"] = 2 * inter / (gt.sum() + res.mask.sum())
            rec["precision"] = inter / max(res.mask.sum(), 1)
            rec["recall"] = inter / max(gt.sum(), 1)
            try:
                rgb = to_float_rgb(res.image)
                f = extract_features(rgb, res.mask)
                rec.update({f"live_sim__{k}": v for k, v in f.items()})
                # protocol v2 / H2: sclera-referenced white balance, same mask
                H, W = res.image.shape[:2]
                x, y, w, h = clamp_box(box)
                wb = estimate_white_balance(res.image, (int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)),
                                            exclude=res.mask)
                rec.update({"wb_found": wb.found, "wb_gain_r": wb.gains_rgb[0], "wb_gain_g": wb.gains_rgb[1],
                            "wb_gain_b": wb.gains_rgb[2]})
                fw = extract_features(apply_gains(rgb, wb), res.mask)
                rec.update({f"live_wb__{k}": v for k, v in fw.items()})
            except ValueError:
                rec["status"] = "few_pixels"
        rows.append(rec)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(df)}", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RESULTS, "live_sim_features.csv"), index=False)
    ok = out[out.status == "ok"]
    summary = {
        "n": int(len(out)), "status_counts": {k: int(v) for k, v in out.status.value_counts().items()},
        "dice_median": float(ok.dice.median()),
        "dice_iqr": [float(ok.dice.quantile(.25)), float(ok.dice.quantile(.75))],
        "precision_median": float(ok.precision.median()), "recall_median": float(ok.recall.median()),
        "quality_percentiles_5_50_95": {
            k: [float(out[f"q_{k}"].quantile(q)) for q in (.05, .5, .95)]
            for k in ("brightness", "clipped_fraction", "sharpness")},
    }
    with open(os.path.join(RESULTS, "live_sim_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
