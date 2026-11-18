"""
main.py
HemoSense FastAPI server.

Endpoints
  GET  /health                  model status + saved metrics
  POST /screen                  upload one eyelid photo -> ANFIS anemia risk + grade + explanation
  POST /screen/batch            upload 1-10 eyelid photos (+ optional boxes) -> verdict + symptoms + diet plan
  GET  /symptoms                symptom checklist for the UI
  POST /screen/roi              upload photo -> raw & fuzzy-corrected ROI images
  POST /diet/recommendations    screening data (or photo) -> LLM dietary guidance
  GET  /diet/usage              in-process LLM request counters per model

Run (repo root; needs numpy, opencv, pillow, fastapi - no tensorflow):
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
from api.schemas import DietPlanRequest, DietRecommendationRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline.load_pipeline()
    yield


app = FastAPI(
    title="HemoSense API",
    version="1.0.0",
    description="Smartphone anemia screening (ANFIS fuzzy model) + dietary intelligence.",
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
            "hint": "Create models/anfis.json with `python -m research.run_experiment` "
                    "or set HEMOSENSE_MODEL_PATH to a valid anfis.json.",
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
@app.post("/screen", tags=["screening"])
async def screen(
    image: Annotated[UploadFile, File(description="Eyelid photo (jpg/png)")],
    box: Annotated[Optional[str], Form(description="Optional JSON [x, y, w, h] in 0..1 over the eyelid")] = None,
):
    """Screens one photo. Rejections return 422 with a machine-readable `code`."""
    img_bytes = await _read_upload(image)
    try:
        result = pipeline.screen_image_bytes(img_bytes, include_roi=True, box=_parse_box(box))
    except pipeline.ImageQualityError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message})
    except ValueError as exc:
        raise _http_bad_from_value_error(exc)
    result["disclaimer"] = DISCLAIMER
    return result


DISCLAIMER = ("Screening only, not a diagnosis. Confirm with a blood test (CBC) "
              "and consult a clinician.")


def _parse_box(raw) -> Optional[list]:
    """Box = [x, y, w, h] as fractions of the (EXIF-rotated) photo; None -> default box."""
    if raw is None or raw == "":
        return None
    try:
        box = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(box, dict):
            box = [box["x"], box["y"], box["w"], box["h"]]
        box = [float(v) for v in box]
        if len(box) != 4 or not all(0.0 <= v <= 1.0 for v in box):
            raise ValueError
        return box
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=400, detail="box must be [x, y, w, h] with values in 0..1")


@app.post("/screen/batch", tags=["screening"])
async def screen_batch(
    images: Annotated[List[UploadFile], File(
        description=f"{clinical.MIN_IMAGES}-{clinical.MAX_IMAGES} eyelid photos of the same person")],
    data: Annotated[Optional[str], Form(
        description='Optional JSON {"user_context": {...}, "roi_boxes": [[x,y,w,h], ...]} '
                    '(boxes in 0..1, one per image, in upload order)')] = None,
):
    """Screens every photo, then aggregates them into one verdict with the typical
    symptoms for the detected grade and a baseline (non-LLM) diet plan."""
    if not (clinical.MIN_IMAGES <= len(images) <= clinical.MAX_IMAGES):
        raise HTTPException(
            status_code=400,
            detail=f"Upload between {clinical.MIN_IMAGES} and {clinical.MAX_IMAGES} "
                   f"photos (got {len(images)}).",
        )

    user_context, boxes = {}, []
    if data:
        try:
            raw = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="data must be valid JSON")
        if not isinstance(raw, dict):
            raise HTTPException(status_code=422, detail="data must be a JSON object")
        boxes = raw.pop("roi_boxes", None) or []
        try:
            req = DietRecommendationRequest.model_validate(raw)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=json.loads(exc.json()))
        if req.user_context:
            user_context = req.user_context.model_dump(exclude_none=True)

    per_image = []
    for idx, image in enumerate(images):
        row = {"index": idx, "filename": image.filename}
        try:
            img_bytes = await _read_upload(image)
            box = _parse_box(boxes[idx]) if idx < len(boxes) else None
            row.update(pipeline.screen_image_bytes(img_bytes, include_roi=True, box=box))
        except pipeline.ImageQualityError as exc:
            row.update(error=exc.message, error_code=exc.code)
        except HTTPException as exc:
            row["error"] = str(exc.detail)
        except ValueError as exc:
            row.update(error=f"Bad image: {exc}", error_code="bad_image")
        per_image.append(row)

    valid = [r for r in per_image if "error" not in r]
    if len(valid) < clinical.MIN_IMAGES:
        first = next((r for r in per_image if r.get("error_code")), per_image[0])
        raise HTTPException(
            status_code=422,
            detail={
                "code": first.get("error_code", "image_quality"),
                "message": first.get("error", "The photo could not be analysed."),
                "per_image": per_image,
            },
        )

    aggregate = clinical.aggregate_screenings(valid, pipeline.confidence_table())
    return {
        "aggregate": aggregate,
        "per_image": per_image,
        "symptoms": clinical.symptom_report(aggregate["severity_class"],
                                            user_context.get("symptoms")),
        "diet_plan": clinical.baseline_diet_plan(aggregate["severity_class"], user_context),
        "model": pipeline.get_state().get("name"),
        "disclaimer": DISCLAIMER,
    }


@app.get("/symptoms", tags=["screening"])
async def symptoms():
    """Symptom checklist the UI shows; ids are sent back in user_context.symptoms."""
    return clinical.symptom_catalog()


@app.post("/screen/roi", tags=["screening"])
async def screen_roi(
    image: Annotated[UploadFile, File(description="Eyelid photo (jpg/png)")],
    box: Annotated[Optional[str], Form(description="Optional JSON [x, y, w, h] in 0..1")] = None,
):
    """Debug helper: the box crop and the segmented conjunctiva as PNG data-URLs."""
    try:
        img_bytes = await _read_upload(image)
        return JSONResponse(content=pipeline.roi_images_b64(img_bytes, _parse_box(box)))
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
                              payload["screening"].get("severity_class") is None):
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
        except pipeline.ImageQualityError as exc:
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Bad image: {exc}")
        payload["screening"] = {
            "severity_class": res["severity_class"],
            "anemic": res["anemic"],
        }
        payload["screening_source"] = "image"

    if (not payload.get("screening")) or payload["screening"].get("severity_class") is None:
        raise HTTPException(
            status_code=400,
            detail="No screening data: provide 'data' with a screening fragment or an 'image'.",
        )
    return payload


@app.post("/diet/recommendations", tags=["diet"])
async def diet_recommendations(
    data: Annotated[Optional[str], Form(
        description='JSON matching the DietRecommendationRequest schema, e.g. '
                    '{"screening": {"severity_class": "Mild", '
                    '"anemic": true}}')] = None,
    image: Annotated[Optional[UploadFile], File(
        description="Optional photo to screen first (alternative to screening data)")] = None,
    model: Annotated[Optional[str], Form(description="Preferred first-choice LLM")] = None,
    max_tokens: Annotated[Optional[int], Form(ge=32, le=2000)] = None,
):
    payload = _build_screening_payload(DietRecommendationRequest, data, image)
    return llm.generate_recommendations(payload, preferred_model=model, max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Personalised diet plan (AI planner grounded in USDA data, rules fallback)
# ---------------------------------------------------------------------------
@app.get("/diet/foods", tags=["diet"])
async def diet_foods():
    """Foods the planner can use (for the app's dislike picker)."""
    from hemosense.diet import food_catalogue
    return food_catalogue()


@app.post("/diet/plan", tags=["diet"])
async def diet_plan(req: DietPlanRequest):
    """AI proposes meals, local dish names and cost estimates using ONLY the verified food list;
    the server rejects anything else and recomputes every nutrient from USDA data. If the AI is
    unavailable or invalid, the rule-based planner answers (generated_by = "rules")."""
    from starlette.concurrency import run_in_threadpool

    from hemosense.diet import ai_brief, evaluate_spec

    ctx = req.user_context.model_dump(exclude_none=True) if req.user_context else {}
    severity = req.severity_class if req.severity_class in clinical.SEVERITY_ORDER else "Normal"
    system, user = ai_brief(ctx, severity)
    holder = {}

    def _validate(obj):
        holder["plan"] = evaluate_spec(ctx, obj, ai_model="pending")
        return obj

    fallback_reason = None
    try:
        out = await run_in_threadpool(llm.chat_json, system, user, _validate, 2200)
        plan = holder["plan"]
        plan["ai_model"] = out["model_used"]
    except llm.LlmError as exc:
        fallback_reason = exc.message
        plan = None
    base = clinical.baseline_diet_plan(severity, ctx)
    if plan is None:
        base["warnings"] = base.get("warnings", []) + [f"AI planner unavailable ({fallback_reason}); "
                                                       "showing the data-driven plan."]
        return base
    keep = {k: base[k] for k in ("goal", "extra_tips", "when_to_see_clinician", "recovery_outlook")}
    return {**plan, **keep}


# ---------------------------------------------------------------------------
# LLM usage
# ---------------------------------------------------------------------------
@app.get("/diet/usage", tags=["diet"])
async def diet_usage():
    return llm.usage.snapshot()