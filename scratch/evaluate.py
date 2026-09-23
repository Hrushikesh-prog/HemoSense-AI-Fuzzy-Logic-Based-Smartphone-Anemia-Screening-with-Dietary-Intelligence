"""
evaluate.py
Shared MAE/RMSE computation, per-lighting-bucket breakdown, and Baseline-A vs Baseline-B
comparison plotting. Used by train.py (per-run eval) and cross_validate.py (step 3.6).
"""

import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config


def _predict_all(model, ds):
    preds, trues = [], []
    for x, y in ds:
        p = model.predict(x, verbose=0)
        preds.append(p.flatten() if p.ndim > 1 else p)
        trues.append(y.numpy())
    return np.concatenate(preds), np.concatenate(trues)


def mae_rmse(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    return mae, rmse


# ---------------------------------------------------------------------------
# Accuracy metrics derived from regression output
#
# The model predicts a continuous Hb value, so "accuracy" is only defined once
# you bin those values into classes. Two binnings are reported:
#
#   1. 4-class severity accuracy — uses the same bins dataset_preparation.py used
#      (Severe/Moderate/Mild/Normal), so it lines up with the severity_class column.
#   2. Binary anemic-vs-not accuracy (Hb < 12.0) — plus sensitivity and specificity,
#      which is what a screening tool is actually judged on and what a biomedical
#      reviewer will expect to see.
#
# Report these ALONGSIDE MAE/RMSE, not instead of them. Accuracy throws away
# information: predicting 11.9 when the truth is 12.1 counts as a full miss even
# though the estimate is excellent. MAE/RMSE stay your primary metrics.
# ---------------------------------------------------------------------------

ANEMIA_THRESHOLD = 12.0  # g/dL. Anemic is treated as Hb <= 12.0 (inclusive) to stay
                          # consistent with dataset_preparation.py's pd.cut bins, where
                          # Mild = (10, 12]. WHO's own cutoff is Hb < 12.0 for non-pregnant
                          # women and 11.0 for pregnant women and under-5s — if your cohort
                          # is specific, change this value and state it in the paper.


def hb_to_severity(values):
    """
    Bin continuous Hb into the same 4 classes dataset_preparation.py used.

    IMPORTANT: dataset_preparation.py calls pd.cut(bins=[0,7,10,12,30], ...) which
    defaults to right=True, i.e. intervals are (0,7], (7,10], (10,12], (12,30].
    So Hb exactly 7.0 is Severe (not Moderate), 10.0 is Moderate, 12.0 is Mild.
    np.digitize(..., right=True) reproduces that; using right=False silently
    disagrees with the severity_class column at every boundary.
    """
    values = np.asarray(values, dtype=np.float64)
    edges = [7.0, 10.0, 12.0]
    names = np.array(["Severe", "Moderate", "Mild", "Normal"])
    idx = np.digitize(values, edges, right=True)
    return names[idx]


def severity_accuracy(y_true, y_pred):
    """4-class accuracy: did the predicted Hb fall in the correct severity band?"""
    true_cls = hb_to_severity(y_true)
    pred_cls = hb_to_severity(y_pred)
    acc = float(np.mean(true_cls == pred_cls))

    # per-class recall, so a high overall number can't hide a class the model never gets
    per_class = {}
    for cls in ["Severe", "Moderate", "Mild", "Normal"]:
        mask = true_cls == cls
        n = int(mask.sum())
        per_class[cls] = {
            "recall": float(np.mean(pred_cls[mask] == cls)) if n else None,
            "n_true": n,
        }
    return {"accuracy": acc, "per_class": per_class}


def binary_screening_metrics(y_true, y_pred, threshold=ANEMIA_THRESHOLD):
    """
    Anemic (Hb < threshold) vs not. Reports accuracy plus sensitivity/specificity —
    for a screening tool, sensitivity (catching true anemia cases) matters more than
    raw accuracy, especially when most of your dataset is 'Normal'.
    """
    # Anemic = Hb <= threshold, NOT < threshold. This matches dataset_preparation.py's
    # pd.cut(right=True) where Mild is (10,12], so exactly 12.0 counts as Mild/anemic.
    # Using strict < here would classify 12.0 as non-anemic and contradict the
    # severity_class column on the same patient.
    true_pos_cls = np.asarray(y_true) <= threshold   # True = anemic
    pred_pos_cls = np.asarray(y_pred) <= threshold

    tp = int(np.sum(true_pos_cls & pred_pos_cls))
    tn = int(np.sum(~true_pos_cls & ~pred_pos_cls))
    fp = int(np.sum(~true_pos_cls & pred_pos_cls))
    fn = int(np.sum(true_pos_cls & ~pred_pos_cls))

    total = tp + tn + fp + fn
    acc = float((tp + tn) / total) if total else None
    sensitivity = float(tp / (tp + fn)) if (tp + fn) else None   # recall on anemic
    specificity = float(tn / (tn + fp)) if (tn + fp) else None
    precision = float(tp / (tp + fp)) if (tp + fp) else None
    f1 = (float(2 * precision * sensitivity / (precision + sensitivity))
          if precision and sensitivity else None)

    return {
        "threshold_g_dl": threshold,
        "accuracy": acc,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def all_metrics(y_true, y_pred):
    """MAE/RMSE + both accuracy flavours, in one dict."""
    mae, rmse = mae_rmse(y_true, y_pred)
    return {
        "mae": mae,
        "rmse": rmse,
        "severity_4class": severity_accuracy(y_true, y_pred),
        "binary_screening": binary_screening_metrics(y_true, y_pred),
    }


def evaluate_and_save(model, test_ds, test_df, run_name, head="regression"):
    if head != "regression":
        # classification path: fall back to keras' own evaluate for accuracy
        results = model.evaluate(test_ds, verbose=0, return_dict=True)
        with open(os.path.join(config.RESULTS_DIR, f"{run_name}_test_metrics.json"), "w") as f:
            json.dump(results, f, indent=2)
        return results

    y_pred, y_true = _predict_all(model, test_ds)
    overall_mae, overall_rmse = mae_rmse(y_true, y_pred)

    sev = severity_accuracy(y_true, y_pred)
    binary = binary_screening_metrics(y_true, y_pred)

    metrics = {
        "overall_mae": overall_mae,
        "overall_rmse": overall_rmse,
        "n_test": len(y_true),
        "severity_4class_accuracy": sev["accuracy"],
        "severity_4class_per_class": sev["per_class"],
        "binary_screening": binary,
    }

    # Breakdown by every available grouping column (severity_class, region, and
    # lighting_bucket when using the step-3.6 manifest). Computed here so every training
    # run already carries it — cross_validate.py aggregates across runs/folds separately.
    # NOTE: relies on test_ds having been built in the same row order as test_df.
    # data_loader.make_dataset does not shuffle when training=False, so order is preserved.
    for col in config.BREAKDOWN_COLUMNS:
        if col not in test_df.columns:
            continue
        buckets = {}
        bucket_arr = test_df[col].astype(str).values[: len(y_true)]
        for bucket in sorted(set(bucket_arr)):
            mask = bucket_arr == bucket
            if mask.sum() == 0:
                continue
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
        metrics[f"per_{col}"] = buckets

    with open(os.path.join(config.RESULTS_DIR, f"{run_name}_test_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    _plot_pred_vs_true(y_true, y_pred, run_name)
    _print_summary(metrics, run_name)
    return metrics


def _fmt(v, nd=3):
    return "n/a" if v is None else f"{v:.{nd}f}"


def _print_summary(metrics, run_name):
    """Console summary so you can read the headline numbers without opening the JSON."""
    b = metrics["binary_screening"]
    print(f"\n=== {run_name} — test set (n={metrics['n_test']}) ===")
    print(f"  MAE  : {_fmt(metrics['overall_mae'])} g/dL")
    print(f"  RMSE : {_fmt(metrics['overall_rmse'])} g/dL")
    print(f"  4-class severity accuracy : {_fmt(metrics['severity_4class_accuracy'])}")
    print(f"  Binary (anemic = Hb <= {b['threshold_g_dl']}) accuracy : {_fmt(b['accuracy'])}")
    print(f"      sensitivity : {_fmt(b['sensitivity'])}   specificity : {_fmt(b['specificity'])}")
    print(f"      confusion   : {b['confusion']}")
    print("  Per-class recall (4-class):")
    for cls, d in metrics["severity_4class_per_class"].items():
        print(f"      {cls:9s} recall={_fmt(d['recall'])}  (n={d['n_true']})")
    print()


def _plot_pred_vs_true(y_true, y_pred, run_name):
    plt.figure(figsize=(5, 5))
    plt.scatter(y_true, y_pred, alpha=0.5, s=15)
    lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    plt.plot(lims, lims, "r--", label="Ideal (y=x)")
    plt.xlabel("True Hb (g/dL)")
    plt.ylabel("Predicted Hb (g/dL)")
    plt.title(f"Predicted vs True — {run_name}")
    plt.legend()
    plt.tight_layout()
    out_path = os.path.join(config.RESULTS_DIR, f"{run_name}_pred_vs_true.png")
    plt.savefig(out_path, dpi=150)
    plt.close()


def compare_baselines(metrics_a_path, metrics_b_path, out_name="baseline_comparison"):
    """
    Load two saved *_test_metrics.json files (Baseline-A and Baseline-B) and produce
    the MAE/RMSE comparison chart your paper's results section needs.
    """
    with open(metrics_a_path) as f:
        a = json.load(f)
    with open(metrics_b_path) as f:
        b = json.load(f)

    # Two panels: error metrics (lower is better) and accuracy metrics (higher is better).
    # Plotting them on one axis would be misleading — different units, opposite directions.
    err_labels = ["MAE", "RMSE"]
    a_err = [a["overall_mae"], a["overall_rmse"]]
    b_err = [b["overall_mae"], b["overall_rmse"]]

    acc_labels = ["4-class acc", "Binary acc", "Sensitivity", "Specificity"]
    a_acc = [a.get("severity_4class_accuracy"),
             a.get("binary_screening", {}).get("accuracy"),
             a.get("binary_screening", {}).get("sensitivity"),
             a.get("binary_screening", {}).get("specificity")]
    b_acc = [b.get("severity_4class_accuracy"),
             b.get("binary_screening", {}).get("accuracy"),
             b.get("binary_screening", {}).get("sensitivity"),
             b.get("binary_screening", {}).get("specificity")]
    a_acc = [0 if v is None else v for v in a_acc]
    b_acc = [0 if v is None else v for v in b_acc]

    width = 0.35
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    x = np.arange(len(err_labels))
    axes[0].bar(x - width / 2, a_err, width, label="Baseline-A (uncorrected)")
    axes[0].bar(x + width / 2, b_err, width, label="Baseline-B (fuzzy-corrected)")
    axes[0].set_xticks(x); axes[0].set_xticklabels(err_labels)
    axes[0].set_ylabel("g/dL error")
    axes[0].set_title("Error (lower is better)")
    axes[0].legend(fontsize=8)

    x2 = np.arange(len(acc_labels))
    axes[1].bar(x2 - width / 2, a_acc, width, label="Baseline-A (uncorrected)")
    axes[1].bar(x2 + width / 2, b_acc, width, label="Baseline-B (fuzzy-corrected)")
    axes[1].set_xticks(x2); axes[1].set_xticklabels(acc_labels, fontsize=8)
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel("score")
    axes[1].set_title("Accuracy (higher is better)")
    axes[1].legend(fontsize=8)

    fig.suptitle("Baseline-A vs Baseline-B")
    fig.tight_layout()
    out_path = os.path.join(config.RESULTS_DIR, f"{out_name}.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    # also print a text table for pasting into the paper
    print(f"\n{'Metric':<22}{'Baseline-A':>12}{'Baseline-B':>12}")
    for name, av, bv in zip(err_labels + acc_labels, a_err + a_acc, b_err + b_acc):
        print(f"{name:<22}{av:>12.3f}{bv:>12.3f}")
    print(f"\n[evaluate] Saved comparison chart to {out_path}")
    return out_path
