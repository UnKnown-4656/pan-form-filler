"""
Centralized application configuration via Pydantic Settings.

All tunable parameters — detection thresholds, paths, server settings — are
configurable via environment variables or a .env file. This prevents
hardcoded magic numbers scattered across modules.

Env var prefix: PDFFILL_  (e.g., PDFFILL_PORT=8080)
"""

from pathlib import Path
from typing import Tuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve project root relative to this file's location.
# config.py is at pdf_autofill/app/config.py → project root is two levels up.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application-wide configuration with sensible defaults for old i5 hardware."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PDFFILL_",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ──────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    MAX_WORKERS: int = Field(
        default=1,
        description="Max concurrent PDF processing tasks. Keep at 1 for old hardware.",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=50,
        description="Maximum upload file size in megabytes.",
    )
    LOG_LEVEL: str = "INFO"

    # ── Paths ───────────────────────────────────────────────────────────────
    EXTRACTED_DIR: Path = Field(default=_PROJECT_ROOT / "extracted")
    OUTPUT_DIR: Path = Field(default=_PROJECT_ROOT / "output")
    TEMPLATES_DIR: Path = Field(default=_PROJECT_ROOT / "app" / "templates")
    MODELS_DIR: Path = Field(default=_PROJECT_ROOT / "models")

    # ── PDF Conversion ──────────────────────────────────────────────────────
    PDF_ZOOM_FACTOR: float = Field(
        default=2.0,
        description=(
            "Zoom factor for PDF→image conversion. "
            "2.0 = 144 DPI (good balance of quality vs speed). "
            "Increase for very small text; decrease for faster processing."
        ),
    )

    # ── Photo Detection ─────────────────────────────────────────────────────
    PHOTO_DETECTION_STRATEGY: str = Field(
        default="auto",
        description=(
            "Which face detection strategy to use: "
            "'haar' = Haar Cascade only, "
            "'dnn' = DNN only, "
            "'auto' = try Haar first, fall back to DNN."
        ),
    )
    # Haar Cascade parameters
    HAAR_SCALE_FACTOR: float = 1.1
    HAAR_MIN_NEIGHBORS: int = 5
    HAAR_MIN_SIZE_W: int = 80
    HAAR_MIN_SIZE_H: int = 80
    # DNN parameters
    DNN_CONFIDENCE_THRESHOLD: float = Field(
        default=0.5,
        description="Minimum confidence score for DNN face detection.",
    )
    DNN_INPUT_SIZE: int = Field(
        default=300,
        description="DNN blob input size (300×300). Smaller = faster, less accurate.",
    )
    # Photo bounding box expansion
    PHOTO_EXPAND_TOP: float = Field(
        default=0.3,
        description="Expand face bbox upward by this ratio (to capture forehead/hair).",
    )
    PHOTO_EXPAND_BOTTOM: float = Field(
        default=0.5,
        description="Expand face bbox downward by this ratio (to capture chin/neck).",
    )
    PHOTO_EXPAND_SIDES: float = Field(
        default=0.4,
        description="Expand face bbox left/right by this ratio.",
    )

    # ── Signature Detection ─────────────────────────────────────────────────
    SIG_FOCUS_LOWER_PERCENT: float = Field(
        default=0.6,
        description="Search bottom N% of each page for signatures.",
    )
    SIG_ADAPTIVE_BLOCK_SIZE: int = 15
    SIG_ADAPTIVE_C: int = 10
    SIG_MORPH_KERNEL_SIZE: int = 5
    SIG_MIN_WIDTH: int = 80
    SIG_MIN_HEIGHT: int = 20
    SIG_MAX_WIDTH_RATIO: float = Field(
        default=0.6,
        description="Max signature width as fraction of page width.",
    )
    SIG_ASPECT_RATIO_MIN: float = 1.5
    SIG_ASPECT_RATIO_MAX: float = 8.0
    SIG_SOLIDITY_MAX: float = 0.7
    SIG_DENSITY_MAX: float = 0.4
    SIG_CONFIDENCE_THRESHOLD: float = Field(
        default=0.3,
        description="Below this confidence, warn that signature may be incorrect.",
    )

    # ── Cleanup ─────────────────────────────────────────────────────────────
    CLEANUP_TTL_HOURS: int = Field(
        default=24,
        description="Auto-delete extracted files older than this many hours.",
    )

    @property
    def haar_min_size(self) -> Tuple[int, int]:
        """Return Haar min size as a tuple for OpenCV."""
        return (self.HAAR_MIN_SIZE_W, self.HAAR_MIN_SIZE_H)

    @property
    def max_upload_bytes(self) -> int:
        """Return max upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# Module-level singleton — import this everywhere.
settings = Settings()
