"""Paired bootstrap non-inferiority of ANFIS vs each baseline (same patients, same folds).

Non-inferiority margin: 0.05 AUC (a common margin for diagnostic-accuracy comparisons).
ANFIS is non-inferior when the lower bound of the 95 % CI of AUC(ANFIS) - AUC(other) > -0.05.

Run:  python -m research.noninferiority
Out:  research/results/noninferiority.csv
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "research", "results")
MARGIN, N_BOOT, SEED = 0.05, 2000, 42


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(R, name))[["pid", "y", "p"]]


def main() -> None:
    rng = np.random.default_rng(SEED)
    a_live, a_exp = load("oof_live_pipeline_ANFIS.csv"), load("oof_expert_palpebral_ANFIS.csv")
    comps = [("live_pipeline", m, a_live, load(f"oof_live_pipeline_{m}.csv"))
             for m in ("Mamdani", "LogReg", "RandomForest")]
    comps.append(("expert_palpebral", "CNN", a_exp, load("oof_cnn.csv")))
    rows = []
    for setting, name, a, b in comps:
        m = a.merge(b, on="pid", suffixes=("_a", "_b"))
        y, pa, pb = m.y_a.values, m.p_a.values, m.p_b.values
        d = roc_auc_score(y, pa) - roc_auc_score(y, pb)
        ds = []
        for _ in range(N_BOOT):
            i = rng.integers(0, len(y), len(y))
            if len(set(y[i])) < 2:
                continue
            ds.append(roc_auc_score(y[i], pa[i]) - roc_auc_score(y[i], pb[i]))
        lo, hi = np.percentile(ds, [2.5, 97.5])
        rows.append({"setting": setting, "comparator": name, "delta_auc": d, "ci_low": lo, "ci_high": hi,
                     "margin": MARGIN, "non_inferior": bool(lo > -MARGIN)})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(R, "noninferiority.csv"), index=False)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
