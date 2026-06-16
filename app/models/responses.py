"""
Pydantic models for API responses.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DetectionInfo(BaseModel):
    """Details about a single detection (photo or signature)."""
    found: bool = Field(..., description="Whether the element was detected.")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Detection confidence score (0.0–1.0).",
    )
    page: int = Field(
        default=-1,
        description="Page index where the element was found (-1 if not found).",
    )
    bbox: Optional[List[int]] = Field(
        default=None,
        description="Bounding box [x, y, width, height] in pixels.",
    )
    path: Optional[str] = Field(
        default=None,
        description="Path to the extracted image file.",
    )
    strategy: Optional[str] = Field(
        default=None,
        description="Detection strategy that was used.",
    )


class ExtractResponse(BaseModel):
    """Response from the /extract endpoint."""
    request_id: str = Field(..., description="Unique request identifier.")
    photo: DetectionInfo = Field(..., description="Photo detection results.")
    signature: DetectionInfo = Field(..., description="Signature detection results.")
    processing_time_ms: float = Field(
        ..., description="Total processing time in milliseconds."
    )


class TemplateInfo(BaseModel):
    """Info about a single form template."""
    name: str
    description: str
    fields: List[str]


class TemplatesResponse(BaseModel):
    """Response from the /templates endpoint."""
    templates: List[TemplateInfo]


class HealthResponse(BaseModel):
    """Response from the /health endpoint."""
    status: str = Field(default="healthy")
    version: str
    models_loaded: Dict[str, bool]
    available_strategies: List[str]
    uptime_seconds: float
    templates_count: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
