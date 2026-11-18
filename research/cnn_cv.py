"""CNN baseline (EfficientNet-B0, ImageNet weights) under the SAME patient-level
5-fold split as the ANFIS experiment (research/results/folds.csv).

Input: one 224x224 masked palpebral crop per participant (research/data/crops/<pid>.png,
written by extract_features.py). Binary target: WHO anemia.

Per outer fold: 15 % of the training fold is held out (stratified) for early stopping,
Platt calibration and the Youden / sens-85 thresholds; the test fold is touched once.
Phase 1 trains the head with the backbone frozen; phase 2 fine-tunes the top 20 layers.

Run:  python -m research.cnn_cv
Out:  research/results/oof_cnn.csv, research/results/cnn_metrics.json
"""

from __future__ import annotations

import json
import os
import sys
import time

import cv2
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hemosense.metrics import (auc_with_ci, brier, delong_test, ece, prop_ci,  # noqa: E402
                               screen_metrics, threshold_for_sensitivity)

RESULTS = os.path.join(ROOT, "research", "results")
CROPS = os.path.join(ROOT, "research", "data", "crops")
SEED = 42


def build(tf):
    inp = tf.keras.Input((224, 224, 3))
    x = tf.keras.layers.RandomFlip("horizontal")(inp)
    x = tf.keras.layers.RandomRotation(0.05)(x)
    x = tf.keras.layers.RandomContrast(0.1)(x)
    base = tf.keras.applications.EfficientNetB0(include_top=False, weights="imagenet", input_shape=(224, 224, 3))
    base.trainable = False
    x = base(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    out = tf.keras.layers.Dense(1, activation="sigmoid")(x)
    m = tf.keras.Model(inp, out)
    m.compile(tf.keras.optimizers.Adam(1e-3), "binary_crossentropy", metrics=[tf.keras.metrics.AUC(name="auc")])
    return m, base


def youden(y, p):
    from sklearn.metrics import roc_curve
    fpr, tpr, thr = roc_curve(y, p)
    return float(thr[np.argmax(tpr - fpr)])


def main() -> None:
    import tensorflow as tf
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    tf.random.set_seed(SEED)
    np.random.seed(SEED)
    folds = pd.read_csv(os.path.join(RESULTS, "folds.csv"))
    feats = pd.read_csv(os.path.join(RESULTS, "features.csv"))[["pid", "anemic", "region"]]
    df = folds.merge(feats, on="pid")
    X = np.stack([cv2.cvtColor(cv2.imread(os.path.join(CROPS, f"{p}.png")), cv2.COLOR_BGR2RGB)
                  for p in df.pid]).astype(np.float32)  # EfficientNet expects 0..255
    y = df.anemic.values.astype(int)
    out = df[["pid", "fold"]].copy()
    out["y"], out["p"], out["tau_youden"], out["tau_sens85"] = y, np.nan, np.nan, np.nan
    t0 = time.time()
    for k in sorted(df.fold.unique()):
        te = (df.fold == k).values
        tr_idx = np.where(~te)[0]
        tr, va = train_test_split(tr_idx, test_size=0.15, stratify=y[tr_idx], random_state=SEED)
        w = {0: len(tr) / (2 * (y[tr] == 0).sum()), 1: len(tr) / (2 * (y[tr] == 1).sum())}
        m, base = build(tf)
        es = tf.keras.callbacks.EarlyStopping("val_loss", patience=6, restore_best_weights=True)
        m.fit(X[tr], y[tr], validation_data=(X[va], y[va]), epochs=40, batch_size=16,
              class_weight=w, callbacks=[es], verbose=0)
        base.trainable = True
        for layer in base.layers[:-20]:
            layer.trainable = False
        m.compile(tf.keras.optimizers.Adam(1e-5), "binary_crossentropy")
        es2 = tf.keras.callbacks.EarlyStopping("val_loss", patience=4, restore_best_weights=True)
        m.fit(X[tr], y[tr], validation_data=(X[va], y[va]), epochs=15, batch_size=16,
              class_weight=w, callbacks=[es2], verbose=0)
        logit = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))  # noqa: E731
        sv = logit(m.predict(X[va], verbose=0).ravel())
        lr = LogisticRegression(C=1e6).fit(sv.reshape(-1, 1), y[va])
        cal = lambda s: lr.predict_proba(s.reshape(-1, 1))[:, 1]  # noqa: E731
        pv = cal(sv)
        out.loc[te, "p"] = cal(logit(m.predict(X[te], verbose=0).ravel()))
        out.loc[te, "tau_youden"] = youden(y[va], pv)
        out.loc[te, "tau_sens85"] = threshold_for_sensitivity(y[va], pv, 0.85)
        print(f"  fold {k}: done ({time.time() - t0:.0f}s)", flush=True)
        tf.keras.backend.clear_session()

    out.to_csv(os.path.join(RESULTS, "oof_cnn.csv"), index=False)
    r = {"n": int(len(y)), **auc_with_ci(y, out.p.values), "brier": brier(y, out.p.values),
         "ece": ece(y, out.p.values)}
    for t in ("tau_sens85", "tau_youden"):
        m_ = screen_metrics(y, out.p.values, out[t].values)
        c = m_["confusion"]
        m_["sensitivity_ci95"] = prop_ci(c["tp"], c["tp"] + c["fn"])
        m_["specificity_ci95"] = prop_ci(c["tn"], c["tn"] + c["fp"])
        r[t] = m_
    an = pd.read_csv(os.path.join(RESULTS, "oof_expert_palpebral_ANFIS.csv"))[["pid", "p"]].rename(columns={"p": "p_anfis"})
    mm = out.merge(an, on="pid")
    r["delong_anfis_expert_vs_cnn"] = delong_test(mm.y.values, mm.p_anfis.values, mm.p.values)
    with open(os.path.join(RESULTS, "cnn_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2)
    print(json.dumps({k: r[k] for k in ("auc", "auc_ci95")}, indent=2), f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
