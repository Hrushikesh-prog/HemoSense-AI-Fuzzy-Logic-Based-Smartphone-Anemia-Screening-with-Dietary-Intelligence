"""
cross_validate.py
Step 3.6 — two related but distinct pieces of evidence:

  1. run_kfold(): pools train+val+test back together and runs K-fold CV (stratified by
     severity_class where possible) to show the model's accuracy isn't a fluke of one split.

  2. evaluate_lighting_robustness(): loads a model you already trained with train.py and
     scores it on the synthetic lighting-bucket manifest from build_lighting_buckets.py.
     This is the number that actually supports the paper's novelty claim: Baseline-B
     (fuzzy-corrected) should show much less MAE spread across lighting buckets than
     Baseline-A (raw), because that's the whole point of the fuzzy correction layer.

NOTE ON CLASS IMBALANCE: this dataset has only ~4 "Severe" examples total across all
splits. StratifiedKFold will fail or be meaningless below that count — this script
automatically falls back to plain KFold if stratification isn't possible, matching what
dataset_preparation.py already does for its own split. Call this out in your limitations
section rather than treating the CV number for "Severe" as reliable.

Usage:
    python cross_validate.py --variant A --folds 5 --epochs_per_fold 15
    python cross_validate.py --variant B --folds 5 --epochs_per_fold 15
    python cross_validate.py --variant A --lighting_only   # skip k-fold, just score an
                                                             # existing model on lighting buckets
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, StratifiedKFold

import config
from data_loader import load_split, make_dataset
from model import build_model
from evaluate import (mae_rmse, _predict_all, severity_accuracy,
                       binary_screening_metrics)


def _pool_all_splits(variant):
    dfs = []
    path_col = None
    for split in ("train", "val", "test"):
        df, path_col = load_split(split, variant)
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True), path_col


def run_kfold(variant, folds=5, epochs_per_fold=15, lr=config.DEFAULT_LR, aug_strength=1.0):
    full_df, path_col = _pool_all_splits(variant)
    print(f"[cv] Pooled {len(full_df)} images for variant {variant} K-fold CV.")

    strat_col = full_df[config.SEVERITY_COL] if config.SEVERITY_COL in full_df.columns else None
    min_class_count = strat_col.value_counts().min() if strat_col is not None else None

    if strat_col is not None and min_class_count is not None and min_class_count >= folds:
        splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=config.SEED)
        split_iter = splitter.split(full_df, strat_col)
        print(f"[cv] Using StratifiedKFold on {config.SEVERITY_COL}.")
    else:
        splitter = KFold(n_splits=folds, shuffle=True, random_state=config.SEED)
        split_iter = splitter.split(full_df)
        print(f"[cv] Falling back to plain KFold — smallest class has "
              f"{min_class_count if min_class_count is not None else 'N/A'} examples, "
              f"fewer than {folds} folds. ('Severe' results will be noisy — flag this in the writeup.)")

    fold_results = []
    bucket_errors = {}  # severity_class (or other breakdown col) -> list of per-fold dicts

    for fold_idx, (train_idx, test_idx) in enumerate(split_iter, 1):
        print(f"\n[cv] Variant {variant} — Fold {fold_idx}/{folds}")
        train_df = full_df.iloc[train_idx].reset_index(drop=True)
        test_df = full_df.iloc[test_idx].reset_index(drop=True)

        train_ds = make_dataset(train_df, path_col, training=True, aug_strength=aug_strength)
        test_ds = make_dataset(test_df, path_col, training=False)

        model = build_model(lr=lr)
        model.fit(train_ds, epochs=epochs_per_fold, verbose=1)

        y_pred, y_true = _predict_all(model, test_ds)
        mae, rmse = mae_rmse(y_true, y_pred)
        sev_acc = severity_accuracy(y_true, y_pred)["accuracy"]
        bin_m = binary_screening_metrics(y_true, y_pred)
        fold_results.append({
            "fold": fold_idx, "mae": mae, "rmse": rmse, "n": len(y_true),
            "severity_4class_accuracy": sev_acc,
            "binary_accuracy": bin_m["accuracy"],
            "sensitivity": bin_m["sensitivity"],
            "specificity": bin_m["specificity"],
        })
        print(f"[cv] Fold {fold_idx} — MAE: {mae:.3f}  RMSE: {rmse:.3f}  "
              f"4-class acc: {sev_acc:.3f}  binary acc: {bin_m['accuracy']:.3f}")

        if config.SEVERITY_COL in test_df.columns:
            bucket_arr = test_df[config.SEVERITY_COL].astype(str).values[: len(y_true)]
            for bucket in sorted(set(bucket_arr)):
                mask = bucket_arr == bucket
                if mask.sum() == 0:
                    continue
                b_mae, b_rmse = mae_rmse(y_true[mask], y_pred[mask])
                bucket_errors.setdefault(bucket, []).append(
                    {"mae": b_mae, "rmse": b_rmse, "n": int(mask.sum())}
                )

    maes = [r["mae"] for r in fold_results]
    rmses = [r["rmse"] for r in fold_results]
    sev_accs = [r["severity_4class_accuracy"] for r in fold_results]
    bin_accs = [r["binary_accuracy"] for r in fold_results if r["binary_accuracy"] is not None]
    senss = [r["sensitivity"] for r in fold_results if r["sensitivity"] is not None]
    specs = [r["specificity"] for r in fold_results if r["specificity"] is not None]

    def _ms(vals):
        return (float(np.mean(vals)), float(np.std(vals))) if vals else (None, None)

    mean_bin, std_bin = _ms(bin_accs)
    mean_sens, std_sens = _ms(senss)
    mean_spec, std_spec = _ms(specs)

    summary = {
        "variant": variant,
        "folds": folds,
        "fold_results": fold_results,
        "mean_mae": float(np.mean(maes)),
        "std_mae": float(np.std(maes)),
        "mean_rmse": float(np.mean(rmses)),
        "std_rmse": float(np.std(rmses)),
        "mean_severity_4class_accuracy": float(np.mean(sev_accs)),
        "std_severity_4class_accuracy": float(np.std(sev_accs)),
        "mean_binary_accuracy": mean_bin,
        "std_binary_accuracy": std_bin,
        "mean_sensitivity": mean_sens,
        "std_sensitivity": std_sens,
        "mean_specificity": mean_spec,
        "std_specificity": std_spec,
        "per_severity_class": {
            bucket: {
                "mean_mae": float(np.mean([r["mae"] for r in runs])),
                "std_mae": float(np.std([r["mae"] for r in runs])),
                "n_folds_present": len(runs),
            }
            for bucket, runs in bucket_errors.items()
        },
    }

    out_path = os.path.join(config.RESULTS_DIR, f"cv_results_{variant}.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    def _pm(mean, std):
        return "n/a" if mean is None else f"{mean:.3f} ± {std:.3f}"

    print(f"\n[cv] Variant {variant} summary across {folds} folds:")
    print(f"      MAE  {_pm(summary['mean_mae'], summary['std_mae'])}   "
          f"RMSE {_pm(summary['mean_rmse'], summary['std_rmse'])}")
    print(f"      4-class acc {_pm(summary['mean_severity_4class_accuracy'], summary['std_severity_4class_accuracy'])}   "
          f"binary acc {_pm(summary['mean_binary_accuracy'], summary['std_binary_accuracy'])}")
    print(f"      sensitivity {_pm(summary['mean_sensitivity'], summary['std_sensitivity'])}   "
          f"specificity {_pm(summary['mean_specificity'], summary['std_specificity'])}")
    print(f"[cv] Saved to {out_path}")
    return summary


def evaluate_lighting_robustness(model_path, variant, run_label=None):
    """
    Scores an already-trained model (from train.py) on the synthetic lighting-bucket
    manifest built by build_lighting_buckets.py. variant selects which path column
    (image_path vs fuzzy_path) matches how the model was trained.
    """
    import tensorflow as tf

    if not os.path.exists(config.LIGHTING_BUCKETS_CSV):
        raise FileNotFoundError(
            f"{config.LIGHTING_BUCKETS_CSV} not found — run build_lighting_buckets.py first."
        )

    df = pd.read_csv(config.LIGHTING_BUCKETS_CSV)
    path_col = "fuzzy_path" if variant == "B" else "image_path"
    df = df[df[path_col].apply(os.path.exists)].reset_index(drop=True)
    if df.empty:
        raise RuntimeError(f"No usable rows in {config.LIGHTING_BUCKETS_CSV} for path column '{path_col}'.")

    ds = make_dataset(df, path_col, training=False, batch_size=16)
    model = tf.keras.models.load_model(model_path)
    y_pred, y_true = _predict_all(model, ds)

    buckets = {}
    bucket_arr = df["lighting_bucket"].values[: len(y_true)]
    for bucket in sorted(set(bucket_arr)):
        mask = bucket_arr == bucket
        b_mae, b_rmse = mae_rmse(y_true[mask], y_pred[mask])
        b_sev = severity_accuracy(y_true[mask], y_pred[mask])
        b_bin = binary_screening_metrics(y_true[mask], y_pred[mask])
        buckets[bucket] = {
            "mae": b_mae,
            "rmse": b_rmse,
            "severity_4class_accuracy": b_sev["accuracy"],
            "binary_accuracy": b_bin["accuracy"],
            "sensitivity": b_bin["sensitivity"],
            "specificity": b_bin["specificity"],
            "n": int(mask.sum()),
        }

    label = run_label or f"variant_{variant}"
    out_path = os.path.join(config.RESULTS_DIR, f"lighting_robustness_{label}.json")
    with open(out_path, "w") as f:
        json.dump(buckets, f, indent=2)

    print(f"\n[cv] Lighting-bucket results for {label}:")
    print(f"  {'bucket':<12}{'MAE':>8}{'RMSE':>8}{'4cls acc':>10}{'bin acc':>9}{'n':>6}")
    for bucket, m in buckets.items():
        ba = "n/a" if m["binary_accuracy"] is None else f"{m['binary_accuracy']:.3f}"
        print(f"  {bucket:<12}{m['mae']:>8.3f}{m['rmse']:>8.3f}"
              f"{m['severity_4class_accuracy']:>10.3f}{ba:>9}{m['n']:>6}")
    mae_spread = np.std([m["mae"] for m in buckets.values()])
    acc_spread = np.std([m["severity_4class_accuracy"] for m in buckets.values()])
    print(f"  -> spread across buckets: MAE std={mae_spread:.3f}, 4-class acc std={acc_spread:.3f}")
    print("     (lower spread = more lighting-robust; this is the headline claim)")
    print(f"[cv] Saved to {out_path}")
    return buckets


def compare_variance_across_buckets(robustness_a_path, robustness_b_path):
    """
    Headline comparison for the paper: does the fuzzy-corrected model (B) hold a
    flatter MAE across lighting buckets than the raw model (A)? Lower std = more robust.
    """
    with open(robustness_a_path) as f:
        a = json.load(f)
    with open(robustness_b_path) as f:
        b = json.load(f)

    rows = []
    for bucket in sorted(set(a) | set(b)):
        rows.append({
            "lighting_bucket": bucket,
            "A_mae": a.get(bucket, {}).get("mae"),
            "B_mae": b.get(bucket, {}).get("mae"),
            "A_4class_acc": a.get(bucket, {}).get("severity_4class_accuracy"),
            "B_4class_acc": b.get(bucket, {}).get("severity_4class_accuracy"),
            "A_binary_acc": a.get(bucket, {}).get("binary_accuracy"),
            "B_binary_acc": b.get(bucket, {}).get("binary_accuracy"),
        })
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))

    a_maes = [v["mae"] for v in a.values()]
    b_maes = [v["mae"] for v in b.values()]
    a_accs = [v["severity_4class_accuracy"] for v in a.values()
              if v.get("severity_4class_accuracy") is not None]
    b_accs = [v["severity_4class_accuracy"] for v in b.values()
              if v.get("severity_4class_accuracy") is not None]

    print(f"\nSpread across lighting buckets (std — lower = more robust):")
    print(f"  MAE          Baseline-A: {np.std(a_maes):.3f}   Baseline-B: {np.std(b_maes):.3f}")
    if a_accs and b_accs:
        print(f"  4-class acc  Baseline-A: {np.std(a_accs):.3f}   Baseline-B: {np.std(b_accs):.3f}")
    print("Lower spread for Baseline-B supports the 'hardware-agnostic / lighting-robust' claim.")

    out_path = os.path.join(config.RESULTS_DIR, "lighting_bucket_comparison.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved comparison table to {out_path}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["A", "B"], required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--epochs_per_fold", type=int, default=15)
    parser.add_argument("--lighting_only", action="store_true",
                         help="Skip k-fold CV; just evaluate an existing model on lighting buckets.")
    parser.add_argument("--model_path", help="Required with --lighting_only")
    args = parser.parse_args()

    if args.lighting_only:
        if not args.model_path:
            raise SystemExit("--lighting_only requires --model_path")
        evaluate_lighting_robustness(args.model_path, args.variant)
    else:
        run_kfold(args.variant, folds=args.folds, epochs_per_fold=args.epochs_per_fold)
