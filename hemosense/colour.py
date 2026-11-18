"""Sclera-referenced white balance (protocol v2, H2).

The white of the eye sits just above the pulled-down lower eyelid. Its bright, low-saturation
pixels are a built-in neutral reference: scaling R, G, B so the sclera becomes grey removes most
of the colour cast of the camera and the light (von Kries diagonal correction), the same idea
as Outlaw et al. 2020 used for jaundice.

All functions are pure. Images are BGR uint8 at the segmenter's working resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

MIN_SCLERA_PX = 300
GAIN_LIMITS = (0.6, 1.6)


@dataclass
class WhiteBalance:
    found: bool
    gains_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    n_pixels: int = 0
    sclera_rgb: tuple[float, float, float] | None = None


def sclera_search_region(shape, box_px) -> tuple[int, int, int, int]:
    """Region above (and slightly overlapping) the user's box: x widened by 25 %,
    from 1.5 box-heights above the box to 30 % into it."""
    H, W = shape[:2]
    x0, y0, x1, y1 = box_px
    bw, bh = x1 - x0, y1 - y0
    return (max(int(x0 - 0.25 * bw), 0), max(int(y0 - 1.5 * bh), 0),
            min(int(x1 + 0.25 * bw), W), min(int(y0 + 0.3 * bh), H))


def estimate_white_balance(img_bgr: np.ndarray, box_px, exclude: np.ndarray | None = None) -> WhiteBalance:
    rx0, ry0, rx1, ry1 = sclera_search_region(img_bgr.shape, box_px)
    reg = img_bgr[ry0:ry1, rx0:rx1]
    if reg.size == 0:
        return WhiteBalance(False)
    hsv = cv2.cvtColor(reg, cv2.COLOR_BGR2HSV).astype(np.float32)
    s, v = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    cand = (s < 0.18) & (v > 0.50) & (v < 0.97)
    if exclude is not None:
        cand &= ~exclude[ry0:ry1, rx0:rx1]
    if cand.sum() < MIN_SCLERA_PX:
        return WhiteBalance(False, n_pixels=int(cand.sum()))
    # largest connected bright region = sclera (drops isolated glints and skin highlights)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), 8)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    sc = lab == k
    if sc.sum() < MIN_SCLERA_PX:
        return WhiteBalance(False, n_pixels=int(sc.sum()))
    px = reg[sc][:, ::-1].astype(np.float32)          # RGB
    vv = px.max(axis=1)
    px = px[vv >= np.median(vv)]                      # brightest half: avoids shadowed sclera
    mean = px.mean(axis=0)
    gains = np.clip(mean.mean() / np.maximum(mean, 1.0), *GAIN_LIMITS)
    return WhiteBalance(True, tuple(float(g) for g in gains), int(sc.sum()), tuple(float(m) for m in mean))


def apply_gains(rgb_float: np.ndarray, wb: WhiteBalance) -> np.ndarray:
    if not wb.found:
        return rgb_float
    return np.clip(rgb_float * np.asarray(wb.gains_rgb, np.float32), 0.0, 1.0)
