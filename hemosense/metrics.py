"""Screening metrics: AUC with bootstrap CI, DeLong test, threshold selection, calibration."""

from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score


def threshold_for_sensitivity(y: np.ndarray, p: np.ndarray, target: float = 0.85) -> float:
    """Largest threshold whose sensitivity on (y, p) is >= target."""
    pos = np.sort(p[y == 1])[::-1]
    if len(pos) == 0:
        return 0.5
    k = int(np.ceil(target * len(pos))) - 1
    return float(pos[min(max(k, 0), len(pos) - 1)])


def screen_metrics(y: np.ndarray, p: np.ndarray, tau: float | np.ndarray) -> dict:
    yhat = (p >= tau).astype(int)
    tp = int(((yhat == 1) & (y == 1)).sum()); fn = int(((yhat == 0) & (y == 1)).sum())
    tn = int(((yhat == 0) & (y == 0)).sum()); fp = int(((yhat == 1) & (y == 0)).sum())
    sens = tp / max(tp + fn, 1); spec = tn / max(tn + fp, 1)
    return {
        "sensitivity": sens, "specificity": spec,
        "ppv": tp / max(tp + fp, 1), "npv": tn / max(tn + fn, 1),
        "accuracy": (tp + tn) / len(y), "balanced_accuracy": (sens + spec) / 2,
        "confusion": {"tp": tp, "fn": fn, "tn": tn, "fp": fp},
    }


def bootstrap_ci(y, p, fn, n: int = 2000, seed: int = 42, alpha: float = 0.05) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    vals = []
    idx = np.arange(len(y))
    for _ in range(n):
        b = rng.choice(idx, len(idx), replace=True)
        if len(np.unique(y[b])) < 2:
            continue
        vals.append(fn(y[b], p[b]))
    return float(np.percentile(vals, 100 * alpha / 2)), float(np.percentile(vals, 100 * (1 - alpha / 2)))


def auc_with_ci(y, p, **kw) -> dict:
    lo, hi = bootstrap_ci(y, p, roc_auc_score, **kw)
    return {"auc": float(roc_auc_score(y, p)), "auc_ci95": [lo, hi]}


def prop_ci(k: int, n: int) -> list[float]:
    """Wilson 95% interval for a proportion (sensitivity/specificity)."""
    if n == 0:
        return [float("nan")] * 2
    z = 1.96
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return [float(c - h), float(c + h)]


def brier(y, p) -> float:
    return float(np.mean((p - y) ** 2))


def ece(y, p, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e)


# ---------------- DeLong (fast, Sun & Xu 2014) ----------------
def _midrank(x):
    j = np.argsort(x)
    z = x[j]
    n = len(x)
    t = np.zeros(n)
    i = 0
    while i < n:
        k = i
        while k < n and z[k] == z[i]:
            k += 1
        t[i:k] = 0.5 * (i + k - 1) + 1
        i = k
    out = np.empty(n)
    out[j] = t
    return out


def delong_test(y: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> dict:
    """Two-sided DeLong test for two correlated ROC AUCs."""
    order = np.argsort(-y, kind="stable")
    y, preds = y[order], np.vstack([p1, p2])[:, order]
    m = int(y.sum()); n = len(y) - m
    tx, ty, tz = (np.empty((2, m)), np.empty((2, n)), np.empty((2, m + n)))
    for r in range(2):
        tx[r] = _midrank(preds[r, :m]); ty[r] = _midrank(preds[r, m:]); tz[r] = _midrank(preds[r])
    aucs = tz[:, :m].sum(1) / m / n - (m + 1) / 2 / n
    v01 = (tz[:, :m] - tx) / n
    v10 = 1 - (tz[:, m:] - ty) / m
    cov = np.cov(v01) / m + np.cov(v10) / n
    var = cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]
    zstat = (aucs[0] - aucs[1]) / np.sqrt(max(var, 1e-12))
    return {"auc1": float(aucs[0]), "auc2": float(aucs[1]), "z": float(zstat),
            "p_value": float(2 * stats.norm.sf(abs(zstat)))}
