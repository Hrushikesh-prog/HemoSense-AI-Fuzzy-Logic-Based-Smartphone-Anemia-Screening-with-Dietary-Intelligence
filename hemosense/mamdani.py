"""Hand-written Mamdani baseline (expert rules, data-derived membership centres).

Inputs: erythema index (EI), CIELAB a*, high-hue ratio (HHR). Rule matrix from
docs/PROJECT_CONTEXT.md:
              a* Low     a* Medium  a* High
    EI Low    Severe     Moderate   Mild
    EI Medium Moderate   Mild       Normal
    EI High   Mild       Normal     Normal
HHR Low raises the level by one; HHR High lowers it by one.
Inference: min (AND), max aggregation, centroid defuzzification on a 0..1 risk axis.
"""

from __future__ import annotations

import numpy as np

LEVELS = ("Normal", "Mild", "Moderate", "Severe")
BASE = np.array([[3, 2, 1], [2, 1, 0], [1, 0, 0]])  # [EI term, a* term] -> level index
UNIVERSE = np.linspace(0, 1, 201)
OUT_CENTRES = (0.1, 0.4, 0.65, 0.9)


def _tri(x, a, b, c):
    return np.maximum(np.minimum((x - a) / (b - a + 1e-12), (c - x) / (c - b + 1e-12)), 0)


OUT_MF = np.stack([_tri(UNIVERSE, c - 0.25, c, c + 0.25) for c in OUT_CENTRES])


class Mamdani:
    features = ("ei", "a", "hhr")

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Mamdani":
        """Low centre = median of anemic group, High = median of normal group (feature-wise)."""
        X = np.asarray(X, float)
        self.c = np.zeros((3, 3))
        self.sign = np.ones(3)
        for k in range(3):
            lo, hi = np.median(X[y == 1, k]), np.median(X[y == 0, k])
            if lo > hi:  # feature is higher in anemic people: flip so 'Low' still means 'pale'
                self.sign[k] = -1
                lo, hi = -lo, -hi
            self.c[k] = (lo, (lo + hi) / 2, hi)
        # width = 1/3 of the Low-High span: a neighbouring term fires at about 0.32 at a centre
        self.s = np.maximum((self.c[:, 2] - self.c[:, 0]) / 3, 1e-6)
        return self

    def _mu(self, v: np.ndarray, k: int) -> np.ndarray:
        """Shouldered Gaussian terms: Low saturates below its centre, High above."""
        v = self.sign[k] * v
        c, s = self.c[k], self.s[k]
        low = np.where(v <= c[0], 1.0, np.exp(-0.5 * ((v - c[0]) / s) ** 2))
        med = np.exp(-0.5 * ((v - c[1]) / s) ** 2)
        high = np.where(v >= c[2], 1.0, np.exp(-0.5 * ((v - c[2]) / s) ** 2))
        return np.stack([low, med, high], -1)

    def risk(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, float))
        m = [self._mu(X[:, k], k) for k in range(3)]
        out = np.zeros(len(X))
        for n in range(len(X)):
            agg = np.zeros_like(UNIVERSE)
            for i in range(3):
                for j in range(3):
                    for h in range(3):
                        lvl = int(np.clip(BASE[i, j] + (1 if h == 0 else -1 if h == 2 else 0), 0, 3))
                        strength = min(m[0][n, i], m[1][n, j], m[2][n, h])
                        agg = np.maximum(agg, np.minimum(strength, OUT_MF[lvl]))
            out[n] = (agg * UNIVERSE).sum() / max(agg.sum(), 1e-12)
        return out
