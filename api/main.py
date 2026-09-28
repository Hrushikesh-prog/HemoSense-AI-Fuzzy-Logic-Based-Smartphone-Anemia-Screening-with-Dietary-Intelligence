"""
main.py
HemoSense FastAPI server.

Endpoints
  GET  /health                  model status + saved metrics
  POST /screen                  upload eye/face photo -> Hb estimate + severity + EI
  POST /screen/batch            upload 2-10 eye photos -> aggregated verdict + symptoms + diet plan
  GET  /symptoms                symptom checklist for the UI
  POST /screen/roi              upload photo -> raw & fuzzy-corrected ROI images
  POST /diet/recommendations    screening data (or photo) -> LLM dietary guidance
  GET  /diet/usage              in-process LLM request counters per model

Run (repo root, project env with tensorflow<2.17):
    uvicorn api.main:app --reload --port 8000
"""

import json
from contextlib import asynccontextmanager
from typing import Annotated, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from api import clinical
from api import config
from api import llm
from api import pipeline
from api.schemas import DietRecommendationRequest, ScreeningResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline.load_pipeline()
    yield


app = FastAPI(
    title="HemoSense API",
    version="1.0.0",
    description="Smartphone anemia screening (CNN) + LLM dietary intelligence.",
    lifespan=lifespan,
)

if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=config.CORS_ORIGINS != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(pipeline.PipelineUnavailableError)
async def _pipeline_unavailable(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "model_unavailable",
            "error": exc.reason,
            "hint": "Run the API in the project environment (Python 3.11/3.12, "
                    "tensorflow<2.17, opencv-python, scikit-fuzzy) or set "
                    "HEMOSENSE_MODEL_PATH to a valid .keras file.",
        },
    )


@app.exception_handler(llm.LlmError)
async def _llm_error(request, exc: llm.LlmError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "llm_unavailable",
            "error": exc.message,
            "failures": exc.failures,
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _read_upload(file: UploadFile) -> bytes:
    if file.content_type not in config.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type '{file.content_type}'. "
                   f"Allowed: {sorted(config.ALLOWED_CONTENT_TYPES)}",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {config.MAX_UPLOAD_MB:.0f} MB limit.",
        )
    return data


def _http_bad_from_value_error(exc: ValueError):
    return HTTPException(status_code=400, detail=f"Bad image: {exc}")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["status"])
async def health():
    state = pipeline.get_state()
    return {
        "status": "ok",
        "model": {
            "name": state.get("name"),
            "loaded": state.get("loaded"),
            "path": config.MODEL_PATH,
            "reason_not_loaded": state.get("reason"),
        },
        "metrics": pipeline.load_metrics(),
        "llm": {
            "configured": bool(config.OPENROUTER_API_KEY),
            "n_models": len(config.LLM_MODELS),
            "models": config.LLM_MODELS,
        },
    }


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------
@app.post("/screen", response_model=ScreeningResult, tags=["screening"])
async def screen(image: Annotated[UploadFile, File(description="Eye/face photo (jpg/png)")]):
    try:
        img_bytes = await _read_upload(image)
        result = pipeline.screen_image_bytes(img_bytes)
    except ValueError as exc:
        raise _http_bad_from_value_error(exc)
    result["disclaimer"] = (
        "Screening estimate only — not a medical diagnosis. Consult a clinician."
    )
    return result


@app.post("/screen/batch", tags=["screening"])
async def screen_batch(
    images: Annotated[List[UploadFile], File(
        description=f"{clinical.MIN_IMAGES}-{clinical.MAX_IMAGES} eye photos of the same person")],
    data: Annotated[Optional[str], Form(
        description='Optional JSON {"user_context": {...}} (age, sex, pregnant, diet, '
                    'region, allergies, symptoms)')] = None,
):
    """Screens every photo, then aggregates them into one verdict with the typical
    symptoms for the detected severity and a baseline (non-LLM) diet plan."""
    if not (clinical.MIN_IMAGES <= len(images) <= clinical.MAX_IMAGES):
        raise HTTPException(
            status_code=400,
            detail=f"Upload between {clinical.MIN_IMAGES} and {clinical.MAX_IMAGES} "
                   f"photos (got {len(images)}).",
        )

    user_context = {}
    if data:
        try:
            req = DietRecommendationRequest.model_validate_json(data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=json.loads(exc.json()))
        if req.user_context:
            user_context = req.user_context.model_dump(exclude_none=True)

    per_image = []
    for idx, image in enumerate(images):
        row = {"index": idx, "filename": image.filename}
        try:
            img_bytes = await _read_upload(image)
            row.update(pipeline.screen_image_bytes(img_bytes, include_roi=True))
        except HTTPException as exc:
            row["error"] = str(exc.detail)
        except ValueError as exc:
            row["error"] = f"Bad image: {exc}"
        per_image.append(row)

    valid = [r for r in per_image if "error" not in r]
    if len(valid) < clinical.MIN_IMAGES:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Only {len(valid)} photo(s) could be analysed; at least "
                           f"{clinical.MIN_IMAGES} are needed.",
                "per_image": per_image,
            },
        )

    aggregate = clinical.aggregate_screenings(valid)
    return {
        "aggregate": aggregate,
        "per_image": per_image,
        "symptoms": clinical.symptom_report(aggregate["severity_class"],
                                            user_context.get("symptoms")),
        "diet_plan": clinical.baseline_diet_plan(aggregate["severity_class"], user_context),
        "model": pipeline.get_state().get("name"),
        "disclaimer": "Screening estimate only — not a medical diagnosis. "
                      "Confirm with a blood test (CBC) and consult a clinician.",
    }


@app.get("/symptoms", tags=["screening"])
async def symptoms():
    """Symptom checklist the UI shows; ids are sent back in user_context.symptoms."""
    return clinical.symptom_catalog()


@app.post("/screen/roi", tags=["screening"])
async def screen_roi(image: Annotated[UploadFile, File(description="Eye/face photo (jpg/png)")]):
    """Debug helper: returns raw + fuzzy-corrected conjunctiva ROIs as PNG data-URLs."""
    try:
        img_bytes = await _read_upload(image)
        return JSONResponse(content=pipeline.roi_images_b64(img_bytes))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Bad image: {exc}")


# ---------------------------------------------------------------------------
# Dietary intelligence (OpenRouter)
# ---------------------------------------------------------------------------
def _build_screening_payload(cls, data_json: Optional[str], image: Optional[UploadFile]):
    request: DietRecommendationRequest
    if data_json:
        try:
            request = DietRecommendationRequest.model_validate_json(data_json)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=json.loads(exc.json()))
    else:
        request = DietRecommendationRequest()

    payload = {"user_context": (request.user_context.model_dump(exclude_none=True)
                                if request.user_context else {})}

    screening = request.screening
    if screening is not None:
        payload["screening"] = screening.model_dump(exclude_none=True)

    if image is not None and (not payload.get("screening") or
                              payload["screening"].get("predicted_hb_gdl") is None):
        # convenience: screen the uploaded photo first, then recommend
        try:
            img_bytes = image.file.read()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Could not read image: {exc}")
        if not img_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(img_bytes) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413,
                                detail=f"Image exceeds {config.MAX_UPLOAD_MB:.0f} MB limit.")
        try:
            res = pipeline.screen_image_bytes(img_bytes)
        except pipeline.PipelineUnavailableError as exc:
            raise HTTPException(status_code=503, detail=f"model_unavailable: {exc.reason}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Bad image: {exc}")
        payload["screening"] = {
            "predicted_hb_gdl": res["predicted_hb_gdl"],
            "severity_class": res["severity_class"],
            "anemic": res["anemic"],
        }
        payload["screening_source"] = "image"

    if (not payload.get("screening")) or payload["screening"].get("predicted_hb_gdl") is None:
        raise HTTPException(
            status_code=400,
            detail="No screening data: provide 'data' with a screening fragment or an 'image'.",
        )
    return payload


@app.post("/diet/recommendations", tags=["diet"])
async def diet_recommendations(
    data: Annotated[Optional[str], Form(
        description='JSON matching the DietRecommendationRequest schema, e.g. '
                    '{"screening": {"predicted_hb_gdl": 11.3, "severity_class": "Mild", '
                    '"anemic": true}}')] = None,
    image: Annotated[Optional[UploadFile], File(
        description="Optional photo to screen first (alternative to screening data)")] = None,
    model: Annotated[Optional[str], Form(description="Preferred first-choice LLM")] = None,
    max_tokens: Annotated[Optional[int], Form(ge=32, le=2000)] = None,
):
    payload = _build_screening_payload(DietRecommendationRequest, data, image)
    return llm.generate_recommendations(payload, preferred_model=model, max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# LLM usage
# ---------------------------------------------------------------------------
@app.get("/diet/usage", tags=["diet"])
async def diet_usage():
    return llm.usage.snapshot()