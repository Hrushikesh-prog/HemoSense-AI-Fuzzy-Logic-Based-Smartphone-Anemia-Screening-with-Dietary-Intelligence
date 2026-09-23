"""
build_lighting_buckets.py
Step 3.6 (data side). Implements the evaluation plan's "synthetically augment ... by
overlaying digital shadows and varied color temperatures" requirement.

For every image in test_split.csv, generates 4 deterministic perturbed copies
(low_light, shadow, warm_temp, cool_temp) plus the untouched original (normal).
Each perturbed copy is then run through the REAL apply_fuzzy_correction from
anemia_pipeline.py, so you get matched pairs: the same perturbed image, with and
without fuzzy correction. That's what lets you show Baseline-B holds steady across
buckets while Baseline-A's error swings — the paper's core novelty claim.

Usage:
    python build_lighting_buckets.py
"""

import os
import sys

import cv2
import numpy as np
import pandas as pd

import config

sys.path.insert(0, config.PIPELINE_DIR)
from anemia_pipeline import apply_fuzzy_correction


def apply_low_light(img):
    return np.clip(img.astype(np.float32) * 0.45, 0, 255).astype(np.uint8)


def apply_shadow(img):
    """Overlays a soft dark ellipse across part of the frame, mimicking a hand/phone shadow."""
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(mask, (int(w * 0.3), int(h * 0.5)), (int(w * 0.4), int(h * 0.7)), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(1.0, w * 0.08))
    out = img.astype(np.float32)
    for c in range(3):
        out[:, :, c] *= (1 - 0.5 * mask)
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_warm_temp(img):
    """Simulates warm indoor/tungsten lighting (BGR order: boost R, cut B)."""
    out = img.astype(np.float32)
    out[:, :, 2] = np.clip(out[:, :, 2] * 1.25, 0, 255)
    out[:, :, 0] = np.clip(out[:, :, 0] * 0.85, 0, 255)
    return out.astype(np.uint8)


def apply_cool_temp(img):
    """Simulates cool fluorescent/overcast lighting (boost B, cut R)."""
    out = img.astype(np.float32)
    out[:, :, 0] = np.clip(out[:, :, 0] * 1.25, 0, 255)
    out[:, :, 2] = np.clip(out[:, :, 2] * 0.85, 0, 255)
    return out.astype(np.uint8)


BUCKET_FUNCS = {
    "normal": lambda img: img,
    "low_light": apply_low_light,
    "shadow": apply_shadow,
    "warm_temp": apply_warm_temp,
    "cool_temp": apply_cool_temp,
}


def build():
    test_csv = config.SPLIT_CSVS["test"]
    if not os.path.exists(test_csv):
        raise FileNotFoundError(f"{test_csv} not found — run dataset_preparation.py first.")

    test_df = pd.read_csv(test_csv)
    rows = []
    n_read_failed = 0

    print(f"[build_lighting_buckets] Perturbing {len(test_df)} test images x "
          f"{len(BUCKET_FUNCS)} buckets = {len(test_df) * len(BUCKET_FUNCS)} outputs...")

    for idx, row in test_df.iterrows():
        raw_path = row["image_path"]
        img = cv2.imread(raw_path)
        if img is None:
            n_read_failed += 1
            continue

        rel = os.path.relpath(raw_path, config.DATASET_ROOT)
        stem, ext = os.path.splitext(rel)

        for bucket, fn in BUCKET_FUNCS.items():
            perturbed = fn(img)

            raw_out = os.path.join(config.LIGHTING_BUCKETS_ROOT, "raw", f"{stem}__{bucket}{ext}")
            os.makedirs(os.path.dirname(raw_out), exist_ok=True)
            cv2.imwrite(raw_out, perturbed)

            corrected = apply_fuzzy_correction(perturbed)
            fuzzy_out = os.path.join(config.LIGHTING_BUCKETS_ROOT, "fuzzy", f"{stem}__{bucket}{ext}")
            os.makedirs(os.path.dirname(fuzzy_out), exist_ok=True)
            cv2.imwrite(fuzzy_out, corrected)

            rows.append({
                "image_path": raw_out,
                "fuzzy_path": fuzzy_out,
                config.LABEL_COL: row[config.LABEL_COL],
                "lighting_bucket": bucket,
                "source_image": raw_path,
            })

        if (idx + 1) % 20 == 0:
            print(f"  {idx + 1}/{len(test_df)} source images done...")

    if n_read_failed:
        print(f"[build_lighting_buckets] WARNING: {n_read_failed} source images failed to read.")

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(config.LIGHTING_BUCKETS_CSV), exist_ok=True)
    out_df.to_csv(config.LIGHTING_BUCKETS_CSV, index=False)
    print(f"[build_lighting_buckets] Saved {len(out_df)} rows -> {config.LIGHTING_BUCKETS_CSV}")


if __name__ == "__main__":
    build()
