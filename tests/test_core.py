"""Unit tests for the shared core (features, labels, ANFIS, Mamdani, metrics, segmenter)."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hemosense.anfis import ANFIS  # noqa: E402
from hemosense.features import extract_features, mask_from_rgba  # noqa: E402
from hemosense.labels import app_grade, group_for, who_grade  # noqa: E402
from hemosense.mamdani import Mamdani  # noqa: E402
from hemosense.metrics import delong_test, screen_metrics, threshold_for_sensitivity  # noqa: E402
from hemosense.segment import segment_conjunctiva  # noqa: E402


# ---------------- labels
@pytest.mark.parametrize("hb,sex,grade", [
    (12.5, "F", "Normal"), (11.5, "F", "Mild"), (12.5, "M", "Mild"), (13.0, "M", "Normal"),
    (9.0, "M", "Moderate"), (7.9, "F", "Severe"), (8.0, "F", "Moderate"),
])
def test_who_grades(hb, sex, grade):
    assert who_grade(hb, group_for(sex, 30)) == grade


def test_app_grade_collapses_moderate_and_severe():
    assert app_grade("Moderate") == app_grade("Severe") == "Moderate-to-Severe"


# ---------------- features
def test_features_known_colour():
    img = np.zeros((40, 40, 3), np.float32)
    img[...] = (0.8, 0.4, 0.4)  # pure-ish red tissue, RGB
    f = extract_features(img, np.ones((40, 40), bool))
    assert f["ei"] == pytest.approx(100 * np.log10(0.8001 / 0.4001), rel=1e-3)
    assert f["hhr"] == pytest.approx(1.0)       # hue 0 deg, S = 0.5 > 0.30
    assert f["sat"] == pytest.approx(0.5, abs=1e-3)
    assert f["a"] > 20


def test_pale_tissue_has_lower_redness_features():
    red = np.full((40, 40, 3), (0.8, 0.35, 0.38), np.float32)
    pale = np.full((40, 40, 3), (0.85, 0.65, 0.65), np.float32)
    m = np.ones((40, 40), bool)
    fr, fp = extract_features(red, m), extract_features(pale, m)
    assert fr["ei"] > fp["ei"] and fr["a"] > fp["a"] and fr["sat"] > fp["sat"]


def test_too_few_pixels_rejected():
    with pytest.raises(ValueError):
        extract_features(np.full((10, 10, 3), 0.5, np.float32), np.ones((10, 10), bool))


def test_mask_encodings():
    alpha = np.zeros((20, 20, 4), np.uint16); alpha[5:10, 5:10] = (100, 200, 30000, 65535)
    assert mask_from_rgba(alpha).sum() == 25
    white = np.full((20, 20, 4), 255, np.uint8); white[5:10, 5:10, :3] = (60, 60, 200)
    assert mask_from_rgba(white).sum() == 25


# ---------------- ANFIS
def _toy(n=200, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    y = (X[:, 0] + 0.5 * X[:, 1] + rng.normal(scale=0.5, size=n) < 0).astype(float)
    return X, y


def test_anfis_gradients_match_finite_differences():
    X, y = _toy(60)
    m = ANFIS(["f0", "f1", "f2"], l2=1e-2)
    m.mean_, m.std_ = X.mean(0), X.std(0)
    xs = m._z(X)
    m.active = np.ones(27, bool)
    m._init_mfs(xs, y); m._lse_consequents(xs, y)
    rng = np.random.default_rng(1)
    m.theta = m.theta + rng.normal(scale=0.3, size=m.theta.shape)
    _, g_c, g_s, g_t = m._loss_grad(xs, y)
    eps = 1e-6
    for arr, g in ((m.centres, g_c), (m.widths, g_s), (m.theta, g_t)):
        for idx in [(0, 0), (1, 2), (2, 1)] if arr.ndim == 2 else [(0,), (13,), (26,)]:
            old = arr[idx]
            arr[idx] = old + eps; lp = m._loss_grad(xs, y)[0]
            arr[idx] = old - eps; lm = m._loss_grad(xs, y)[0]
            arr[idx] = old
            assert g[idx] == pytest.approx((lp - lm) / (2 * eps), rel=1e-3, abs=1e-7)


def test_anfis_learns_and_roundtrips(tmp_path):
    X, y = _toy(300)
    m = ANFIS(["f0", "f1", "f2"]).fit(X[:240], y[:240], X[240:], y[240:])
    assert m.n_params == 45
    p = m.predict_proba(X[240:])
    from sklearn.metrics import roc_auc_score
    assert roc_auc_score(y[240:], p) > 0.85
    path = tmp_path / "m.json"
    m.save(str(path))
    m2 = ANFIS.load(str(path))
    assert np.allclose(m2.predict_proba(X[:5]), m.predict_proba(X[:5]))
    assert len(m.explain(X[0])) == 3


# ---------------- Mamdani
def test_mamdani_risk_orders_pale_above_red():
    X = np.array([[20, 25, 0.1], [40, 40, 0.6]] * 20, float)
    y = np.array([1, 0] * 20)
    m = Mamdani().fit(X, y)
    r = m.risk(np.array([[20, 25, 0.1], [40, 40, 0.6]]))
    assert r[0] > 0.6 > 0.3 > r[1]


# ---------------- metrics
def test_threshold_for_sensitivity_reaches_target():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200); p = rng.random(200) * 0.5 + 0.4 * y
    t = threshold_for_sensitivity(y, p, 0.85)
    assert screen_metrics(y, p, t)["sensitivity"] >= 0.85


def test_delong_identical_predictions():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 100); p = rng.random(100) + y
    r = delong_test(y, p, p.copy())
    assert r["auc1"] == pytest.approx(r["auc2"])


# ---------------- segmentation / quality gate
def _synthetic_eye(dark=False):
    img = np.full((600, 800, 3), (150, 170, 210), np.uint8)       # skin-ish (BGR)
    import cv2
    # pink-red tissue: a curved half-moon band, as a pulled-down lower eyelid looks
    cv2.ellipse(img, (400, 230), (250, 120), 0, 20, 160, (90, 90, 200), 45)
    img[150:250, 250:550] = (235, 235, 235)                        # sclera above it
    rng = np.random.default_rng(0)
    img = np.clip(img + rng.normal(0, 12, img.shape), 0, 255).astype(np.uint8)  # texture (not blurry)
    return (img * 0.08).astype(np.uint8) if dark else img


def test_segmenter_finds_tissue_in_box():
    res = segment_conjunctiva(_synthetic_eye(), (0.15, 0.35, 0.7, 0.35))
    assert res.ok, res.code
    assert res.mask[338:350, 380:420].mean() > 0.5   # bottom of the half-moon band found
    assert res.mask[160:240, 260:540].mean() < 0.05  # sclera excluded


def test_round_red_blob_is_rejected_as_not_crescent():
    """A nose/cheek-like compact red blob under an eye must not pass as an eyelid."""
    import cv2
    rng = np.random.default_rng(0)
    img = np.full((600, 800, 3), (120, 140, 190), np.uint8)
    cv2.ellipse(img, (400, 180), (140, 50), 0, 0, 360, (230, 230, 235), -1)
    cv2.ellipse(img, (400, 380), (110, 110), 0, 0, 360, (95, 105, 200), -1)
    img = np.clip(img + rng.normal(0, 10, img.shape), 0, 255).astype(np.uint8)
    res = segment_conjunctiva(img, (0.25, 0.4, 0.5, 0.45))
    assert not res.ok and res.code == "not_crescent"


def test_tiny_box_asks_to_move_closer():
    res = segment_conjunctiva(_synthetic_eye(), (0.4, 0.5, 0.03, 0.03))
    assert not res.ok and res.code == "too_far"


def test_quality_gate_rejects_dark_photo():
    res = segment_conjunctiva(_synthetic_eye(dark=True), (0.15, 0.35, 0.7, 0.35))
    assert not res.ok and res.code == "too_dark"


def test_quality_gate_rejects_blur():
    import cv2
    blurry = cv2.GaussianBlur(_synthetic_eye(), (0, 0), 12)
    res = segment_conjunctiva(blurry, (0.15, 0.35, 0.7, 0.35))
    assert not res.ok and res.code == "blurry"
