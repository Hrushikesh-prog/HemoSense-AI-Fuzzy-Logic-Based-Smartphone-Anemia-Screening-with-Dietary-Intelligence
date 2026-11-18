"""Colour features computed on conjunctiva pixels.

All functions are pure. Input images are float RGB in [0, 1]; masks are boolean.

Features (see docs/PROJECT_CONTEXT.md section 2):
  ei   erythema index, 100 * (log10 mean R - log10 mean G)
  a    mean CIELAB a* (redness)
  hhr  high-hue ratio: share of pixels with hue within +/-15 deg of red and S > 0.30
  sat  mean HSV saturation
Extra descriptive features (not fuzzy inputs by default): L (mean L*), b (mean b*).
"""

from __future__ import annotations

import cv2
import numpy as np

FEATURES = ("ei", "a", "hhr", "sat")
EXTRA_FEATURES = ("L", "b")
MIN_PIXELS = 200


def to_float_rgb(img: np.ndarray, bgr: bool = True) -> np.ndarray:
    """uint8/uint16 BGR(A) or RGB(A) -> float32 RGB in [0, 1]."""
    if img.dtype == np.uint16:
        x = img.astype(np.float32) / 65535.0
    elif img.dtype == np.uint8:
        x = img.astype(np.float32) / 255.0
    else:
        x = np.clip(img.astype(np.float32), 0.0, 1.0)
    x = x[..., :3]
    if bgr:
        x = x[..., ::-1]
    return np.ascontiguousarray(x)


def mask_from_rgba(img: np.ndarray) -> np.ndarray:
    """Segmentation mask from an Eyes-defy-anemia crop PNG.

    Encodings seen in the dataset: (1) alpha = 0 on the background (RGB black);
    (2) alpha opaque (or partially opaque) with a white background. The union rule
    "alpha > 0 and not white and not black" handles all of them.
    """
    rgb = img[..., :3].astype(np.float32)
    top = float(np.iinfo(img.dtype).max) if img.dtype.kind == "u" else 1.0
    white = rgb.min(axis=-1) >= 0.97 * top
    black = rgb.max(axis=-1) <= 0.03 * top
    keep = ~(white | black)
    if img.ndim == 3 and img.shape[2] == 4:
        keep &= img[..., 3] > 0
    return keep


def valid_pixel_mask(rgb: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Drop specular highlights and near-black pixels inside the mask."""
    v = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    s = np.where(v > 0, (v - mn) / np.maximum(v, 1e-6), 0.0)
    ok = (v > 0.06) & ~((v > 0.92) & (s < 0.12))
    if mask is not None:
        ok &= mask
    return ok


def extract_features(rgb: np.ndarray, mask: np.ndarray | None = None) -> dict[str, float]:
    """Compute all features on the masked conjunctiva pixels of a float RGB image."""
    ok = valid_pixel_mask(rgb, mask)
    if ok.sum() < MIN_PIXELS:
        raise ValueError(f"too few conjunctiva pixels ({int(ok.sum())})")
    px = rgb[ok].astype(np.float32)  # (N, 3)
    eps = 1e-4
    r_mean, g_mean = float(px[:, 0].mean()), float(px[:, 1].mean())
    ei = 100.0 * (np.log10(r_mean + eps) - np.log10(g_mean + eps))

    lab = cv2.cvtColor(px.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    hsv = cv2.cvtColor(px.reshape(-1, 1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3)
    hue, sat = hsv[:, 0], hsv[:, 1]  # hue in degrees [0, 360), sat in [0, 1]
    red_hue = (hue <= 15.0) | (hue >= 345.0)
    hhr = float(np.mean(red_hue & (sat > 0.30)))

    return {
        "ei": float(ei),
        "a": float(lab[:, 1].mean()),
        "hhr": hhr,
        "sat": float(sat.mean()),
        "L": float(lab[:, 0].mean()),
        "b": float(lab[:, 2].mean()),
        "n_pixels": int(ok.sum()),
    }
