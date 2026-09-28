"""
schemas.py
Pydantic request/response models for the HemoSense API.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# /screen
# ---------------------------------------------------------------------------
class RoiStatus(BaseModel):
    detected: bool
    note: Optional[str] = Field(default=None, description="Fallback-crop warning, if any")


class ScreeningResult(BaseModel):
    predicted_hb_gdl: float = Field(..., description="Estimated hemoglobin in g/dL")
    severity_class: str = Field(..., description="Severe | Moderate | Mild | Normal")
    anemic: bool = Field(..., description="True when predicted Hb <= 12.0 g/dL")
    erythema_index: Dict[str, Optional[float]] = Field(
        default_factory=lambda: {"raw": None, "corrected": None},
        description="Erythema index before and after fuzzy correction",
    )
    roi: RoiStatus = Field(default_factory=lambda: RoiStatus(detected=True, note=None))
    processing_ms: float
    model: str


# ---------------------------------------------------------------------------
# /diet/recommendations
# ---------------------------------------------------------------------------
class ScreeningFragment(BaseModel):
    predicted_hb_gdl: Optional[float] = None
    severity_class: Optional[str] = None
    anemic: Optional[bool] = None


class UserContext(BaseModel):
    age: Optional[int] = None
    sex: Optional[str] = Field(default=None, description="male | female")
    pregnant: Optional[bool] = None
    diet: Optional[str] = Field(default=None, description="omnivore | vegetarian | vegan")
    region: Optional[str] = None
    allergies: Optional[List[str]] = None
    symptoms: Optional[List[str]] = Field(default=None, description="Self-reported symptom ids (GET /symptoms)")


class DietRecommendationRequest(BaseModel):
    screening: Optional[ScreeningFragment] = None
    user_context: Optional[UserContext] = None
    model: Optional[str] = Field(default=None, description="Preferred first-choice LLM (fallback chain still applies)")
    max_tokens: Optional[int] = Field(default=None, ge=32, le=2000)


DietRecommendationRequest.model_rebuild()


class DietRecommendationResponse(BaseModel):
    recommendations: str
    model_used: str
    attempts: List[str]
    failures: List[Dict[str, str]] = Field(default_factory=list)
    disclaimer: str


class LlmUsageRow(BaseModel):
    model: str
    requests: int


class LlmUsage(BaseModel):
    today: List[LlmUsageRow]
    last_hour: int