"""
File management utilities.

Handles:
- Per-request temporary directories (UUID-based isolation)
- Safe filename generation
- TTL-based cleanup of old extracted files
- Directory creation with error handling
"""

import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class FileManager:
    """
    Manages file I/O for the extraction and output pipeline.

    Each processing request gets its own UUID-named subdirectory under
    the extracted/ folder, preventing collisions in concurrent requests.
    """

    def __init__(
        self,
        extracted_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.extracted_dir = extracted_dir or settings.EXTRACTED_DIR
        self.output_dir = output_dir or settings.OUTPUT_DIR
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create base directories if they don't exist."""
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(
            "Directories verified: extracted=%s, output=%s",
            self.extracted_dir,
            self.output_dir,
        )

    def create_request_dir(self, request_id: Optional[str] = None) -> Path:
        """
        Create an isolated directory for a single processing request.

        Args:
            request_id: Optional pre-generated UUID. If None, a new one is created.

        Returns:
            Path to the request-specific directory.
        """
        request_id = request_id or str(uuid.uuid4())
        request_dir = self.extracted_dir / request_id
        request_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created request directory: %s", request_dir)
        return request_dir

    def get_photo_path(self, request_dir: Path) -> Path:
        """Return the standard path for the extracted photo."""
        return request_dir / "photo.png"

    def get_signature_path(self, request_dir: Path) -> Path:
        """Return the standard path for the extracted signature."""
        return request_dir / "signature.png"

    def get_thumb_path(self, request_dir: Path) -> Path:
        """Return the standard path for the extracted thumb impression."""
        return request_dir / "thumb.png"

    def get_output_path(self, request_id: str, template_name: str) -> Path:
        """
        Return the path for the completed PDF output.

        Args:
            request_id: UUID of the processing request.
            template_name: Name of the form template used.

        Returns:
            Path like output/<request_id>_<template_name>.pdf
        """
        safe_name = template_name.replace(" ", "_").replace("/", "_")
        filename = f"{request_id}_{safe_name}.pdf"
        return self.output_dir / filename

    def save_temp_pdf(self, pdf_bytes: bytes, request_dir: Path) -> Path:
        """
        Save uploaded PDF bytes to a temp file in the request directory.

        Args:
            pdf_bytes: Raw PDF file content.
            request_dir: Request-specific directory.

        Returns:
            Path to the saved temporary PDF file.
        """
        temp_path = request_dir / "source.pdf"
        temp_path.write_bytes(pdf_bytes)
        logger.debug("Saved temp PDF: %s (%d bytes)", temp_path, len(pdf_bytes))
        return temp_path

    def cleanup_request(self, request_dir: Path) -> None:
        """
        Remove a request directory and all its contents.

        Safe to call even if the directory doesn't exist.
        """
        if request_dir.exists():
            shutil.rmtree(request_dir, ignore_errors=True)
            logger.info("Cleaned up request directory: %s", request_dir)

    def cleanup_old_files(self, max_age_hours: Optional[int] = None) -> int:
        """
        Remove request directories older than the TTL.

        Args:
            max_age_hours: Override the configured TTL. Uses settings if None.

        Returns:
            Number of directories removed.
        """
        max_age = max_age_hours or settings.CLEANUP_TTL_HOURS
        cutoff_time = time.time() - (max_age * 3600)
        removed_count = 0

        if not self.extracted_dir.exists():
            return 0

        for item in self.extracted_dir.iterdir():
            if item.is_dir():
                try:
                    # Use directory modification time as proxy for request time.
                    if item.stat().st_mtime < cutoff_time:
                        shutil.rmtree(item, ignore_errors=True)
                        removed_count += 1
                        logger.info("Cleaned up old directory: %s", item)
                except OSError as e:
                    logger.warning("Failed to clean up %s: %s", item, e)

        if removed_count > 0:
            logger.info("Cleanup complete: removed %d old directories", removed_count)

        return removed_count

    @staticmethod
    def generate_request_id() -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())
