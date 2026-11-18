"""Live-path conjunctiva segmentation + image-quality gate.

Input: a full BGR photo and a box (normalised x, y, w, h in [0, 1]) that the user
places over the pulled-down lower eyelid in the app. Output: a boolean mask of the
palpebral conjunctiva inside the photo, or a rejection code.

Rejection codes (match the app): too_dark, overexposed, blurry, no_conjunctiva.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

WORK_MAX_SIDE = 900          # segment on a downscaled copy for speed
DEFAULT_BOX = (0.14, 0.42, 0.72, 0.44)  # matches the app's default review box


@dataclass
class SegResult:
    ok: bool
    code: str | None = None
    message: str | None = None
    mask: np.ndarray | None = None     # bool mask at the *working* resolution
    image: np.ndarray | None = None    # BGR uint8 working image
    quality: dict | None = None
    sclera: object | None = None       # hemosense.colour.WhiteBalance found above the eyelid


MESSAGES = {
    "too_dark": "The photo is too dark. Turn on the torch or move to brighter light.",
    "overexposed": "The photo is overexposed (glare). Move the light slightly to the side.",
    "blurry": "The photo is blurry. Hold the phone steady and tap to focus on the eyelid.",
    "no_conjunctiva": "Could not find the pink inner eyelid inside the box. Pull the lower "
                      "eyelid down gently and place the box over the pink area.",
    "no_eye": "This does not look like an eyelid: there is no white of the eye just above the "
              "box. Place the box on the pink inner eyelid, right under the eye.",
    "not_crescent": "The red area found is not the thin half-moon of the inner eyelid (it looks like "
                    "skin or another object). Pull the lower eyelid down, move closer, and draw a "
                    "small box around just the pink half-moon.",
    "too_far": "The eyelid is too small in the photo. Hold the phone 10-15 cm from the eye "
               "so the pink eyelid fills the box.",
}

MIN_BOX_PX = 40

# Crescent prior. On all 215 dataset photos the segmented conjunctiva has elongation
# (length^2 / area) >= 2.9, solidity (area / convex-hull area) <= 0.80 and width/height >= 1.24
# (research/tmp/shape_stats.py); a nose, cheek or shirt patch is a compact blob.
CRESCENT = {"min_elongation": 2.7, "max_solidity": 0.85, "min_width_height": 1.1}


def crescent_shape(mask: np.ndarray) -> dict:
    """Elongation, solidity and bbox width/height of a single-component mask."""
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    (_, _), (w, h), _ = cv2.minAreaRect(c)
    area = float(mask.sum())
    hull = cv2.contourArea(cv2.convexHull(c))
    _, _, bw, bh = cv2.boundingRect(c)
    return {"elongation": max(w, h) ** 2 / max(area, 1.0), "solidity": area / max(hull, 1.0),
            "width_height": bw / max(bh, 1)}


def is_crescent(sh: dict) -> bool:
    return (sh["elongation"] >= CRESCENT["min_elongation"] and sh["solidity"] <= CRESCENT["max_solidity"]
            and sh["width_height"] >= CRESCENT["min_width_height"])


def _best_crescent(mask: np.ndarray, min_area: int) -> tuple[np.ndarray | None, dict | None]:
    """Largest connected component that has the crescent shape (None if there is none)."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    order = sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA])
    first = None
    for i in order:
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            break
        comp = lab == i
        sh = crescent_shape(comp)
        first = first or sh
        if is_crescent(sh):
            return comp, sh
    return None, first   # shortest box side at the working resolution (900 px max side)


def clamp_box(box) -> tuple[float, float, float, float]:
    if box is None:
        return DEFAULT_BOX
    x, y, w, h = (float(v) for v in box)
    x, y = min(max(x, 0.0), 0.95), min(max(y, 0.0), 0.95)
    w, h = min(max(w, 0.05), 1.0 - x), min(max(h, 0.05), 1.0 - y)
    return x, y, w, h


def _working(bgr: np.ndarray) -> np.ndarray:
    s = WORK_MAX_SIDE / max(bgr.shape[:2])
    if s < 1:
        bgr = cv2.resize(bgr, (int(bgr.shape[1] * s), int(bgr.shape[0] * s)), interpolation=cv2.INTER_AREA)
    return bgr


def quality(bgr_box: np.ndarray) -> dict:
    hsv = cv2.cvtColor(bgr_box, cv2.COLOR_BGR2HSV)
    v = hsv[..., 2].astype(np.float32) / 255.0
    gray = cv2.cvtColor(bgr_box, cv2.COLOR_BGR2GRAY)
    # blur measured at a fixed scale so it does not depend on the box size
    g = cv2.resize(gray, (320, int(320 * gray.shape[0] / max(gray.shape[1], 1)) or 1))
    return {
        "brightness": float(v.mean()),
        "clipped_fraction": float((v > 0.98).mean()),
        "sharpness": float(cv2.Laplacian(g, cv2.CV_64F).var()),
    }


GC_MAX_SIDE = 360   # GrabCut working size (speed: ~0.2 s per photo on a laptop CPU)
OTSU_MIN_GAP = 8.0  # a* units between the two Otsu classes before we split them

QUALITY_LIMITS = {"min_brightness": 0.15, "max_clipped": 0.25, "min_sharpness": 12.0}


def gate(q: dict) -> str | None:
    if q["brightness"] < QUALITY_LIMITS["min_brightness"]:
        return "too_dark"
    if q["clipped_fraction"] > QUALITY_LIMITS["max_clipped"]:
        return "overexposed"
    if q["sharpness"] < QUALITY_LIMITS["min_sharpness"]:
        return "blurry"
    return None


def _largest_components(mask: np.ndarray, keep_frac: float = 0.25) -> np.ndarray:
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return mask
    areas = stats[1:, cv2.CC_STAT_AREA]
    big = areas.max()
    keep = [i + 1 for i, a in enumerate(areas) if a >= keep_frac * big]
    return np.isin(lab, keep)


def segment_conjunctiva(bgr: np.ndarray, box=None, check_quality: bool = True) -> SegResult:
    img = _working(bgr)
    H, W = img.shape[:2]
    x, y, w, h = clamp_box(box)
    x0, y0, x1, y1 = int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)
    if min(x1 - x0, y1 - y0) < MIN_BOX_PX:
        return SegResult(False, "too_far", MESSAGES["too_far"])
    roi = img[y0:y1, x0:x1]
    q = quality(roi)
    if check_quality and (code := gate(q)):
        return SegResult(False, code, MESSAGES[code], quality=q)

    # 1) GrabCut seeded by the user's box. For speed it runs on a crop around the box
    #    (15 % margin for background samples), downscaled to <= GC_MAX_SIDE px.
    fg = np.zeros((H, W), bool)
    mx, my = int(0.15 * (x1 - x0)) + 4, int(0.15 * (y1 - y0)) + 4
    cx0, cy0, cx1, cy1 = max(x0 - mx, 0), max(y0 - my, 0), min(x1 + mx, W), min(y1 + my, H)
    crop = img[cy0:cy1, cx0:cx1]
    sc = min(1.0, GC_MAX_SIDE / max(crop.shape[:2]))
    small = cv2.resize(crop, (max(int(crop.shape[1] * sc), 8), max(int(crop.shape[0] * sc), 8)),
                       interpolation=cv2.INTER_AREA) if sc < 1 else crop
    rx0, ry0 = int((x0 - cx0) * sc), int((y0 - cy0) * sc)
    rect = (max(rx0, 1), max(ry0, 1),
            max(min(int((x1 - x0) * sc), small.shape[1] - rx0 - 2), 2),
            max(min(int((y1 - y0) * sc), small.shape[0] - ry0 - 2), 2))
    gc_mask = np.zeros(small.shape[:2], np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(small, gc_mask, rect, bgd, fgd, 4, cv2.GC_INIT_WITH_RECT)
        fg_small = np.isin(gc_mask, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
        fg[cy0:cy1, cx0:cx1] = cv2.resize(fg_small, (crop.shape[1], crop.shape[0]),
                                          interpolation=cv2.INTER_NEAREST).astype(bool)
    except cv2.error:
        fg[y0:y1, x0:x1] = True

    # 2) colour refinement: conjunctiva is red/pink tissue -> high a* relative to the box,
    #    not dark (lashes), not white (sclera, glare), reasonably saturated.
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    a = lab[..., 1] - 128.0
    s, v = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    inbox = np.zeros((H, W), bool)
    inbox[y0:y1, x0:x1] = True
    # The a* cut is RELATIVE (Otsu split of the smoothed a* of the candidates, applied only
    # when the candidates really hold two colour populations) with a low absolute floor,
    # so very pale (severely anemic) eyelids are not rejected.
    cand = fg & inbox & (v > 0.15) & ~((v > 0.92) & (s < 0.15)) & (s > 0.15)
    if cand.sum() > 50:
        a_s = cv2.GaussianBlur(a, (0, 0), 3)
        vals = a_s[cand]
        lo, hi = float(vals.min()), float(vals.max())
        u8 = np.clip((vals - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
        t, _ = cv2.threshold(u8.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thr = lo + t / 255 * (hi - lo)
        if vals[vals >= thr].mean() - vals[vals < thr].mean() > OTSU_MIN_GAP:
            cand &= a_s >= thr
        cand &= a_s >= 8.0
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    min_area = int(max(150, 0.02 * inbox.sum()))
    if cand.sum() < min_area:
        return SegResult(False, "no_conjunctiva", MESSAGES["no_conjunctiva"], quality=q, image=img)

    # crescent prior: keep the largest half-moon-shaped region, reject compact blobs
    crescent, shape = _best_crescent(cand, min_area)
    q = {**q, **{f"shape_{k}": round(v, 3) for k, v in (shape or {}).items()}}
    if crescent is None:
        if check_quality:
            return SegResult(False, "not_crescent", MESSAGES["not_crescent"], quality=q, image=img)
        crescent = _largest_components(cand)
    cand = crescent

    # 3) plausibility: a pulled-down lower eyelid always has the white of the eye (sclera)
    #    just above it. Red objects elsewhere (lips, skin, clothing) do not.
    from hemosense.colour import estimate_white_balance
    sclera = estimate_white_balance(img, (x0, y0, x1, y1), exclude=cand)
    if check_quality and not sclera.found:
        return SegResult(False, "no_eye", MESSAGES["no_eye"], quality=q, image=img, sclera=sclera)
    return SegResult(True, mask=cand, image=img, quality=q, sclera=sclera)
