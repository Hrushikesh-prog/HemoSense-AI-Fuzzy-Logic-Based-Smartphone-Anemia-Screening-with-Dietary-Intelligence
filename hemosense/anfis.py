"""Zero-order Sugeno ANFIS for binary screening (pure numpy, no deep-learning deps).

Structure: K inputs x 3 Gaussian terms (Low / Medium / High) -> 3**K rules.
Rule r fires with w_r = prod_k mu_{k, j_k(r)}(x_k); output logit z = sum_r wbar_r * theta_r,
p = sigmoid(a * z + b) after Platt calibration.
For K = 3 there are 9 centres + 9 widths + 27 consequents = 45 trainable parameters.

Training (Jang-style hybrid): consequents initialised by ridge least squares on the
normalised firing strengths, then all parameters refined with Adam on binary
cross-entropy + L2 on consequents, with early stopping on a validation split.
Rules whose mean normalised firing strength is below `prune_below` are pruned.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field

import numpy as np

TERMS = ("Low", "Medium", "High")


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


@dataclass
class ANFIS:
    features: list[str]
    n_terms: int = 3
    l2: float = 1e-2
    lr: float = 0.01
    max_epochs: int = 800
    patience: int = 60
    prune_below: float = 0.005
    seed: int = 42
    # learned
    mean_: np.ndarray | None = None
    std_: np.ndarray | None = None
    centres: np.ndarray | None = None   # (K, T)
    widths: np.ndarray | None = None    # (K, T)
    theta: np.ndarray | None = None     # (R,)
    active: np.ndarray | None = None    # (R,) bool
    platt_a: float = 1.0
    platt_b: float = 0.0
    platt_c_male: float = 0.0   # v2 (H1): sex term in the calibration; 0 = v1 behaviour
    tau: float = 0.5
    best_epoch: int = 0
    history: list = field(default_factory=list)

    # ---------------- structure ----------------
    @property
    def rules(self) -> np.ndarray:
        K = len(self.features)
        return np.array(list(itertools.product(range(self.n_terms), repeat=K)))  # (R, K)

    def _z(self, x: np.ndarray) -> np.ndarray:
        return (np.asarray(x, float) - self.mean_) / self.std_

    def _forward(self, xs: np.ndarray):
        """xs standardised (n, K). Returns logit z, normalised firing wbar, and log-mu."""
        d = xs[:, :, None] - self.centres[None]                 # (n, K, T)
        logmu = -0.5 * (d / self.widths[None]) ** 2             # (n, K, T)
        R = self.rules
        logw = logmu[:, np.arange(len(self.features))[None, :], R].sum(-1)  # (n, R)
        logw = np.where(self.active[None], logw, -np.inf)
        logw -= logw.max(axis=1, keepdims=True)
        w = np.exp(logw)
        wbar = w / w.sum(axis=1, keepdims=True)
        return wbar @ self.theta, wbar, d

    # ---------------- training ----------------
    def _init_mfs(self, xs: np.ndarray, y: np.ndarray) -> None:
        K = xs.shape[1]
        c = np.zeros((K, self.n_terms))
        for k in range(K):
            lo, hi = np.median(xs[y == 1, k]), np.median(xs[y == 0, k])
            lo, hi = min(lo, hi), max(lo, hi)
            if hi - lo < 0.5:  # medians too close: spread over the data range instead
                lo, hi = np.percentile(xs[:, k], [20, 80])
            c[k] = np.linspace(lo, hi, self.n_terms)
        self.centres = c
        spacing = np.maximum(np.diff(c, axis=1).mean(axis=1, keepdims=True), 0.3)
        self.widths = np.repeat(spacing * 0.85, self.n_terms, axis=1)

    def _lse_consequents(self, xs: np.ndarray, y: np.ndarray) -> None:
        self.theta = np.zeros(len(self.rules))
        _, wbar, _ = self._forward(xs)
        target = np.where(y == 1, 2.0, -2.0)
        A = wbar.T @ wbar + 0.1 * np.eye(wbar.shape[1])
        self.theta = np.linalg.solve(A, wbar.T @ target)

    def _loss_grad(self, xs, y):
        z, wbar, d = self._forward(xs)
        p = _sigmoid(z)
        n = len(y)
        eps = 1e-7
        loss = -np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)) + self.l2 * np.sum(self.theta ** 2)
        dz = (p - y) / n                                        # (n,)
        g_theta = wbar.T @ dz + 2 * self.l2 * self.theta
        # dz/dlogw_r = wbar_r (theta_r - z); dlogw_r/dc_kj = (x-c)/s^2 if rule uses term j on input k
        gw = dz[:, None] * wbar * (self.theta[None] - z[:, None])  # (n, R)
        K, T = self.centres.shape
        g_c = np.zeros((K, T))
        g_s = np.zeros((K, T))
        R = self.rules
        for k in range(K):
            for j in range(T):
                sel = R[:, k] == j
                gk = gw[:, sel].sum(axis=1)                     # (n,)
                dk = d[:, k, j]
                s = self.widths[k, j]
                g_c[k, j] = np.sum(gk * dk / s ** 2)
                g_s[k, j] = np.sum(gk * dk ** 2 / s ** 3)
        return loss, g_c, g_s, g_theta

    def fit(self, X: np.ndarray, y: np.ndarray, X_val=None, y_val=None, epochs: int | None = None) -> "ANFIS":
        X, y = np.asarray(X, float), np.asarray(y, float)
        self.mean_, self.std_ = X.mean(0), X.std(0) + 1e-9
        xs = self._z(X)
        self.active = np.ones(self.n_terms ** X.shape[1], bool)
        self._init_mfs(xs, y)
        self._lse_consequents(xs, y)

        params = [self.centres, self.widths, self.theta]
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        b1, b2 = 0.9, 0.999
        xv = self._z(X_val) if X_val is not None else None
        best = (np.inf, None, 0)
        n_ep = epochs or self.max_epochs
        for ep in range(1, n_ep + 1):
            loss, *grads = self._loss_grad(xs, y)
            for i, (p, g) in enumerate(zip(params, grads)):
                m[i] = b1 * m[i] + (1 - b1) * g
                v[i] = b2 * v[i] + (1 - b2) * g * g
                p -= self.lr * (m[i] / (1 - b1 ** ep)) / (np.sqrt(v[i] / (1 - b2 ** ep)) + 1e-8)
            np.clip(self.widths, 0.15, 5.0, out=self.widths)
            if xv is not None:
                pv = _sigmoid(self._forward(xv)[0])
                vl = -np.mean(y_val * np.log(pv + 1e-7) + (1 - y_val) * np.log(1 - pv + 1e-7))
                self.history.append((ep, float(loss), float(vl)))
                if vl < best[0] - 1e-5:
                    best = (vl, [p.copy() for p in params], ep)
                elif ep - best[2] > self.patience:
                    break
        if best[1] is not None:
            self.centres, self.widths, self.theta = best[1]
            self.best_epoch = best[2]
        else:
            self.best_epoch = n_ep
        self._prune(xs)
        return self

    def _prune(self, xs: np.ndarray) -> None:
        _, wbar, _ = self._forward(xs)
        self.active = wbar.mean(0) >= self.prune_below

    # ---------------- inference ----------------
    def logit(self, X: np.ndarray) -> np.ndarray:
        return self._forward(self._z(np.atleast_2d(X)))[0]

    def predict_proba(self, X: np.ndarray, male=None) -> np.ndarray:
        """Calibrated probability. `male` (bool or array) only matters for sex-aware (v2) models."""
        z = self.platt_a * self.logit(X) + self.platt_b
        if male is not None and self.platt_c_male:
            z = z + self.platt_c_male * np.asarray(male, float)
        return _sigmoid(z)

    def rule_strengths(self, x: np.ndarray) -> np.ndarray:
        return self._forward(self._z(np.atleast_2d(x)))[1][0]

    def memberships(self, x: np.ndarray) -> dict:
        xs = self._z(np.atleast_2d(x))[0]
        mu = np.exp(-0.5 * ((xs[:, None] - self.centres) / self.widths) ** 2)
        return {f: dict(zip(TERMS, map(float, mu[k]))) for k, f in enumerate(self.features)}

    def explain(self, x: np.ndarray, top: int = 3) -> list[dict]:
        """Top firing rules for one sample, in linguistic form."""
        wbar = self.rule_strengths(x)
        out = []
        for r in np.argsort(-wbar)[:top]:
            ante = {f: TERMS[j] for f, j in zip(self.features, self.rules[r])}
            out.append({"if": ante, "weight": float(wbar[r]),
                        "risk": float(_sigmoid(self.platt_a * self.theta[r] + self.platt_b))})
        return out

    @property
    def n_params(self) -> int:
        return int(self.centres.size + self.widths.size + self.theta.size)

    # ---------------- (de)serialisation ----------------
    def to_dict(self, **extra) -> dict:
        return {
            "type": "anfis-sugeno0", "features": self.features, "terms": list(TERMS),
            "mean": self.mean_.tolist(), "std": self.std_.tolist(),
            "centres": self.centres.tolist(), "widths": self.widths.tolist(),
            "theta": self.theta.tolist(), "active": self.active.astype(int).tolist(),
            "platt_a": self.platt_a, "platt_b": self.platt_b, "platt_c_male": self.platt_c_male,
            "tau": self.tau, **extra,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ANFIS":
        m = cls(features=list(d["features"]), n_terms=len(d["terms"]))
        m.mean_, m.std_ = np.array(d["mean"]), np.array(d["std"])
        m.centres, m.widths = np.array(d["centres"]), np.array(d["widths"])
        m.theta, m.active = np.array(d["theta"]), np.array(d["active"], bool)
        m.platt_a, m.platt_b, m.tau = float(d["platt_a"]), float(d["platt_b"]), float(d["tau"])
        m.platt_c_male = float(d.get("platt_c_male", 0.0))
        return m

    def save(self, path: str, **extra) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(**extra), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "ANFIS":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
