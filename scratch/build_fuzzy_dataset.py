"""
build_fuzzy_dataset.py
Run this once, AFTER dataset_preparation.py, BEFORE train.py.

Applies anemia_pipeline.apply_fuzzy_correction (your teammate's actual Phase-2 fuzzy
color-correction function) to every image referenced in train_split.csv / val_split.csv /
test_split.csv, writes the corrected copies to a mirrored folder tree, and saves enriched
manifests (train_split_fuzzy.csv etc.) with a new `fuzzy_path` column.

This means Baseline-B trains on the real output of your teammate's fuzzy logic controller —
not a re-implementation — so the comparison in your paper is honest.

Usage:
    python build_fuzzy_dataset.py
"""

import os
import sys

import cv2
import pandas as pd

import config

sys.path.insert(0, config.PIPELINE_DIR)
try:
    from anemia_pipeline import apply_fuzzy_correction
except ImportError as e:
    raise ImportError(
        "Could not import apply_fuzzy_correction from anemia_pipeline.py. "
        f"Make sure anemia_pipeline.py is in {config.PIPELINE_DIR} "
        "(config.PIPELINE_DIR) and its dependencies (opencv-python, scikit-fuzzy) are installed."
    ) from e


def mirror_path(raw_path, dataset_root, fuzzy_root):
    """Maps .../datasetanemia/India/12/foo.png -> .../datasetanemia_fuzzy/India/12/foo.png"""
    rel = os.path.relpath(raw_path, dataset_root)
    return os.path.join(fuzzy_root, rel)


def process_split(split_name, csv_path, dataset_root, fuzzy_root):
    if not os.path.exists(csv_path):
        print(f"[build_fuzzy_dataset] SKIP: {csv_path} not found.")
        return None

    df = pd.read_csv(csv_path)
    fuzzy_paths = []
    n_failed = 0
    n_skipped_existing = 0

    print(f"[build_fuzzy_dataset] Processing {split_name} ({len(df)} images)...")
    for i, raw_path in enumerate(df["image_path"], 1):
        fuzzy_path = mirror_path(raw_path, dataset_root, fuzzy_root)
        os.makedirs(os.path.dirname(fuzzy_path), exist_ok=True)

        if os.path.exists(fuzzy_path):
            fuzzy_paths.append(fuzzy_path)
            n_skipped_existing += 1
            continue

        img = cv2.imread(raw_path)
        if img is None:
            print(f"  [WARNING] could not read: {raw_path}")
            fuzzy_paths.append("")
            n_failed += 1
            continue

        corrected = apply_fuzzy_correction(img)
        cv2.imwrite(fuzzy_path, corrected)
        fuzzy_paths.append(fuzzy_path)

        if i % 50 == 0 or i == len(df):
            print(f"  {i}/{len(df)} done...")

    df["fuzzy_path"] = fuzzy_paths
    if n_failed:
        print(f"  [build_fuzzy_dataset] {n_failed} images failed to read in {split_name}")
    if n_skipped_existing:
        print(f"  [build_fuzzy_dataset] {n_skipped_existing} already existed, skipped re-processing")

    out_path = csv_path.replace(".csv", "_fuzzy.csv")
    df.to_csv(out_path, index=False)
    print(f"[build_fuzzy_dataset] Saved -> {out_path}\n")
    return out_path


if __name__ == "__main__":
    os.makedirs(config.FUZZY_ROOT, exist_ok=True)
    for split_name, csv_path in config.SPLIT_CSVS.items():
        process_split(split_name, csv_path, config.DATASET_ROOT, config.FUZZY_ROOT)
    print("[build_fuzzy_dataset] Done. You can now run train.py --variant B")
