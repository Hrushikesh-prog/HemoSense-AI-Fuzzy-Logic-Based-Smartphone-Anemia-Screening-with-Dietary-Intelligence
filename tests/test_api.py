"""End-to-end API tests (FastAPI TestClient). Needs models/anfis.json.

Uses a real dataset photo when the dataset is present (skipped otherwise), plus
synthetic images for the rejection paths.
"""

import io
import json
import os
import sys

import cv2
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "models", "anfis.json")),
                                reason="models/anfis.json not built yet")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from api.main import app
    with TestClient(app) as c:
        yield c


def _jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


def _dataset_photo_and_box():
    from hemosense.data import load_participants
    from hemosense.features import mask_from_rgba
    try:
        df, _ = load_participants()
    except Exception:  # noqa: BLE001
        pytest.skip("dataset not available")
    r = df.iloc[0]
    m = mask_from_rgba(cv2.imread(r.palpebral_png, cv2.IMREAD_UNCHANGED))
    ys, xs = np.where(m)
    H, W = m.shape
    box = [max(xs.min() / W - 0.05, 0), max(ys.min() / H - 0.05, 0),
           min((xs.max() - xs.min()) / W + 0.1, 1), min((ys.max() - ys.min()) / H + 0.1, 1)]
    photo = cv2.imread(r.photo)
    photo = cv2.resize(photo, (photo.shape[1] // 3, photo.shape[0] // 3))  # phone-like size
    return _jpeg(photo), box


def test_health_reports_anfis(client):
    r = client.get("/health").json()
    assert r["model"]["loaded"] is True, r["model"]
    assert "anfis" in r["model"]["name"]


def test_batch_single_real_photo(client):
    img, box = _dataset_photo_and_box()
    data = json.dumps({"user_context": {"age": 30, "sex": "female", "diet": "vegetarian"},
                       "roi_boxes": [box]})
    r = client.post("/screen/batch", files=[("images", ("a.jpg", img, "image/jpeg"))], data={"data": data})
    assert r.status_code == 200, r.text
    j = r.json()
    agg = j["aggregate"]
    assert 0 <= agg["p_anemic"] <= 1
    assert agg["severity_class"] in ("Normal", "Mild", "Moderate")
    assert agg["predicted_hb_gdl"] is None
    pi = j["per_image"][0]
    assert len(pi["explanation"]["top_rules"]) == 3
    assert pi["roi_thumbnail"].startswith("data:image/png;base64,")
    assert j["diet_plan"]["iron_rich_foods"]


def test_batch_three_photos_aggregate(client):
    img, box = _dataset_photo_and_box()
    files = [("images", (f"{i}.jpg", img, "image/jpeg")) for i in range(3)]
    r = client.post("/screen/batch", files=files, data={"data": json.dumps({"roi_boxes": [box] * 3})})
    assert r.status_code == 200, r.text
    assert r.json()["aggregate"]["n_used"] == 3
    assert r.json()["aggregate"]["agreement"] == 1.0


def test_dark_photo_rejected_with_code(client):
    dark = np.full((600, 800, 3), 8, np.uint8)
    r = client.post("/screen/batch", files=[("images", ("d.jpg", _jpeg(dark), "image/jpeg"))])
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["code"] == "too_dark" and "dark" in d["message"].lower()


def test_no_eyelid_rejected(client):
    rng = np.random.default_rng(0)
    grey = np.clip(rng.normal(128, 30, (600, 800, 3)), 0, 255).astype(np.uint8)  # textured, colourless
    r = client.post("/screen/batch", files=[("images", ("g.jpg", _jpeg(grey), "image/jpeg"))])
    assert r.status_code == 422
    assert r.json()["detail"]["code"] in ("no_conjunctiva", "blurry")


def test_mixed_batch_skips_bad_photo(client):
    img, box = _dataset_photo_and_box()
    dark = _jpeg(np.full((600, 800, 3), 8, np.uint8))
    files = [("images", ("a.jpg", img, "image/jpeg")), ("images", ("d.jpg", dark, "image/jpeg"))]
    r = client.post("/screen/batch", files=files, data={"data": json.dumps({"roi_boxes": [box, box]})})
    assert r.status_code == 200
    j = r.json()
    assert j["aggregate"]["n_used"] == 1
    assert j["per_image"][1]["error_code"] == "too_dark"


def test_garbage_upload_is_400_or_422(client):
    r = client.post("/screen/batch", files=[("images", ("x.jpg", b"not an image", "image/jpeg"))])
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "bad_image"


def test_bad_box_rejected(client):
    img, _ = _dataset_photo_and_box()
    r = client.post("/screen", files={"image": ("a.jpg", img, "image/jpeg")}, data={"box": "[0.5, 2, 3]"})
    assert r.status_code == 400


def test_exif_rotation_is_applied():
    from PIL import Image

    from api.pipeline import _decode_bgr
    im = Image.new("RGB", (400, 200), (200, 50, 50))
    exif = im.getexif()
    exif[0x0112] = 6  # rotate 90 CW on display
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    assert _decode_bgr(buf.getvalue()).shape[:2] == (400, 200)


def test_diet_requires_severity_not_hb(client):
    # no external LLM call here: a request without a severity is rejected before any call
    r = client.post("/diet/recommendations", data={"data": json.dumps({"screening": {"anemic": True}})})
    assert r.status_code == 400
    from api.main import _build_screening_payload
    from api.schemas import DietRecommendationRequest
    p = _build_screening_payload(DietRecommendationRequest,
                                 json.dumps({"screening": {"severity_class": "Mild", "anemic": True}}), None)
    assert p["screening"]["severity_class"] == "Mild" and "predicted_hb_gdl" not in p["screening"]
