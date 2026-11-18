"""Evidence-based confidence: how often was the deployed decision rule right, in patient-level
cross-validation, for results of similar certainty?

certainty = max(p, 1 - p) of the calibrated ANFIS probability (live pipeline, rule p >= 0.5).
Bins of certainty -> observed accuracy (Wilson 95 % CI) and n. The server reports, for each new
result, the accuracy observed for out-of-fold patients in the same bin, and a label:
  High   = observed accuracy >= 0.90
  Medium = 0.75 <= accuracy < 0.90
  Low    = accuracy < 0.75

Run:  python -m research.confidence_table
Out:  models/confidence.json (served with the model), research/results/confidence_table.csv
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hemosense.metrics import prop_ci  # noqa: E402

EDGES = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
LABELS = [(0.90, "High"), (0.75, "Medium"), (0.0, "Low")]


def label_for(acc: float) -> str:
    return next(lbl for cut, lbl in LABELS if acc >= cut)


def main() -> None:
    o = pd.read_csv(os.path.join(ROOT, "research", "results", "oof_live_pipeline_ANFIS.csv"))
    cert = np.maximum(o.p, 1 - o.p).values
    correct = ((o.p.values >= 0.5).astype(int) == o.y.values)
    rows = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = (cert >= lo) & (cert < hi)
        n, k = int(m.sum()), int(correct[m].sum())
        acc = k / n if n else None
        rows.append({"certainty_from": lo, "certainty_to": min(hi, 1.0), "n": n, "correct": k,
                     "accuracy": acc, "ci95": prop_ci(k, n) if n else None,
                     "label": label_for(acc) if n else "Low"})
    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(ROOT, "research", "results", "confidence_table.csv"), index=False)
    out = {"source": "patient-level 5-fold CV, live pipeline, ANFIS, rule p >= 0.5, n = %d" % len(o),
           "label_rule": "High >= 90 % observed accuracy, Medium 75-90 %, Low < 75 %",
           "bins": rows}
    with open(os.path.join(ROOT, "models", "confidence.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
