"""
pipeline.py
Serving glue between FastAPI and the shared HemoSense core (`hemosense/`).

Live path for one photo:
  decode (EXIF orientation applied, same as the phone's display)
  -> quality gate (too_dark / overexposed / blurry)
  -> conjunctiva segmentation inside the user's box (GrabCut + colour refinement)
  -> colour features (EI, a*, HHR, saturation) on the segmented pixels
  -> ANFIS (anemia) + ANFIS (moderate-or-severe), Platt-calibrated
  -> grade Normal / Mild / Moderate (shown as Moderate-to-Severe) + top fuzzy rules

Only numpy / OpenCV / Pillow are needed: no TensorFlow at serving time.
The model is the single file models/anfis.json written by research/run_experiment.py.
Images are processed in memory and never written to disk.
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
from typing import Optional

from api import config

_state = {"models": None, "loaded": False, "reason": None, "name": None, "loaded_at": None, "meta": None}


class PipelineUnavailableError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ImageQualityError(ValueError):
    """Photo rejected by the quality gate or the segmenter. `code` matches the app."""

    def __init__(self, code: str, message: str, quality: Optional[dict] = None):
        self.code, self.message, self.quality = code, message, quality
        super().__init__(message)


def load_pipeline():
    """Called once from the FastAPI lifespan. Loads models/anfis.json."""
    _state.update(loaded=False, reason=None, name=None)
    if not os.path.exists(config.MODEL_PATH):
        _state["reason"] = (f"Model file not found: {config.MODEL_PATH}. "
                            "Run `python -m research.run_experiment` to create models/anfis.json.")
        return _state
    try:
        import cv2  # noqa: F401
        from hemosense.anfis import ANFIS
        with open(config.MODEL_PATH, encoding="utf-8") as f:
            meta = json.load(f)
        _state["models"] = {k: ANFIS.from_dict(v) for k, v in meta["models"].items()}
    except Exception as exc:  # noqa: BLE001
        _state["reason"] = f"Model unavailable: {type(exc).__name__}: {exc}"
        return _state
    conf_path = os.path.join(os.path.dirname(config.MODEL_PATH), "confidence.json")
    _state["confidence"] = None
    if os.path.exists(conf_path):
        with open(conf_path, encoding="utf-8") as f:
            _state["confidence"] = json.load(f)
    _state.update(loaded=True, meta=meta, loaded_at=time.time(),
                  name=f"anfis-sugeno0 v{meta.get('version', '?')}")
    return _state


def get_state() -> dict:
    return {k: v for k, v in _state.items() if k not in ("models", "confidence")}


def confidence_table() -> Optional[dict]:
    return _state.get("confidence")


def load_metrics() -> dict:
    meta = _state.get("meta") or {}
    return {
        "model": "ANFIS (zero-order Sugeno, 3 inputs x 3 Gaussian terms)",
        "trained_on": meta.get("trained_on"),
        "n_train": meta.get("n_train"),
        "created": meta.get("created"),
        "cv_live_pipeline": meta.get("cv_live_pipeline"),
        "features": {k: m.get("features") for k, m in (meta.get("models") or {}).items()},
    }


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def _decode_bgr(img_bytes: bytes):
    """Decode with EXIF orientation applied, so the user's box (drawn on the displayed
    photo) lines up with the pixels."""
    import numpy as np
    from PIL import Image, ImageOps

    try:
        im = Image.open(io.BytesIO(img_bytes))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"could not decode the image ({type(exc).__name__})") from exc
    if min(im.size) < 64:
        raise ValueError("image is too small")
    rgb = np.asarray(im)
    return np.ascontiguousarray(rgb[..., ::-1])


def _png_b64(bgr) -> Optional[str]:
    import cv2

    ok, buf = cv2.imencode(".png", bgr)
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii") if ok else None


def _overlay_thumbnail(img, mask, box, max_side: int = 320) -> Optional[str]:
    """Crop around the box, tint the segmented conjunctiva, for the 'Why?' screen."""
    import cv2
    import numpy as np

    from hemosense.segment import clamp_box

    H, W = img.shape[:2]
    x, y, w, h = clamp_box(box)
    x0, y0, x1, y1 = int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)
    ov = img.copy()
    tint = np.array([60, 200, 60], np.float32)
    ov[mask] = (ov[mask] * 0.55 + tint * 0.45).astype(np.uint8)
    crop = ov[y0:y1, x0:x1]
    s = min(1.0, max_side / max(crop.shape[:2]))
    if s < 1:
        crop = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), max(1, int(crop.shape[0] * s))),
                          interpolation=cv2.INTER_AREA)
    return _png_b64(crop)


# ---------------------------------------------------------------------------
# Screening one photo
# ---------------------------------------------------------------------------
def screen_image_bytes(img_bytes: bytes, include_roi: bool = False, box=None) -> dict:
    if not _state["loaded"]:
        raise PipelineUnavailableError(_state["reason"] or "model not loaded")
    from hemosense.features import extract_features, to_float_rgb
    from hemosense.segment import MESSAGES, clamp_box, segment_conjunctiva

    t0 = time.time()
    bgr = _decode_bgr(img_bytes)
    seg = segment_conjunctiva(bgr, box)
    if not seg.ok:
        raise ImageQualityError(seg.code, seg.message, seg.quality)
    try:
        f = extract_features(to_float_rgb(seg.image), seg.mask)
    except ValueError:
        raise ImageQualityError("no_conjunctiva", MESSAGES["no_conjunctiva"], seg.quality)

    m_a, m_s = _state["models"]["anemic"], _state["models"]["mod_sev"]
    xa = [[f[k] for k in m_a.features]]
    xs = [[f[k] for k in m_s.features]]
    p_a = float(m_a.predict_proba(xa)[0])
    p_s = float(m_s.predict_proba(xs)[0])
    anemic = p_a >= m_a.tau
    severity = "Normal" if not anemic else ("Moderate" if p_s >= m_s.tau else "Mild")

    result = {
        "anemic": bool(anemic),
        "p_anemic": round(p_a, 4),
        "p_moderate_or_severe": round(p_s, 4),
        "threshold": round(m_a.tau, 4),
        "threshold_mod_sev": round(m_s.tau, 4),
        "severity_class": severity,
        "severity_label": "Moderate-to-Severe" if severity == "Moderate" else severity,
        "predicted_hb_gdl": None,  # ANFIS screens; it does not estimate Hb (never shown)
        "features": {k: round(float(f[k]), 4) for k in ("ei", "a", "hhr", "sat")},
        "erythema_index": {"raw": round(float(f["ei"]), 3), "corrected": None},
        "explanation": {
            "inputs": m_a.features,
            "memberships": m_a.memberships(xa[0]),
            "top_rules": m_a.explain(xa[0], top=3),
        },
        "quality": {k: round(v, 3) for k, v in (seg.quality or {}).items()},
        "roi": {"detected": True, "note": None, "box": list(clamp_box(box)),
                "conjunctiva_pixels": int(seg.mask.sum())},
        "processing_ms": round((time.time() - t0) * 1000, 1),
        "model": _state["name"],
    }
    if include_roi:
        result["roi_thumbnail"] = _overlay_thumbnail(seg.image, seg.mask, box)
    return result


def roi_images_b64(img_bytes: bytes, box=None) -> dict:
    """Debug helper for POST /screen/roi: the box crop and the segmentation overlay."""
    from hemosense.segment import clamp_box, segment_conjunctiva

    bgr = _decode_bgr(img_bytes)
    seg = segment_conjunctiva(bgr, box, check_quality=False)
    img = seg.image if seg.image is not None else bgr
    H, W = img.shape[:2]
    x, y, w, h = clamp_box(box)
    crop = img[int(y * H):int((y + h) * H), int(x * W):int((x + w) * W)]
    return {
        "ok": seg.ok, "code": seg.code, "quality": seg.quality,
        "roi_raw": _png_b64(crop),
        "roi_segmented": _overlay_thumbnail(img, seg.mask, box) if seg.ok else None,
    }
