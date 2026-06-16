"""
Main orchestration service — coordinates the full processing pipeline.

This is the central service that ties together:
- PDF conversion
- Photo detection
- Signature detection
- Template engine (form filling)

It manages the per-request lifecycle: create temp dir → process → cleanup.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.config import settings
from app.services.photo_detector import PhotoDetector
from app.services.signature_detector import SignatureDetector
from app.services.template_engine import TemplateEngine
from app.strategies.base import DetectionResult
from app.utils.file_manager import FileManager
from app.utils.pdf_converter import PDFConverter

logger = logging.getLogger(__name__)


class ProcessingService:
    """
    Orchestrates the full PDF auto-completion pipeline.

    Thread-safe: each request gets its own isolated directory and
    operates on its own data. No shared mutable state between requests.

    Usage:
        service = ProcessingService()
        result = service.extract(pdf_bytes)
        output_path = service.process(pdf_bytes, "PAN_FORM_V1", form_pdf_bytes)
    """

    def __init__(self) -> None:
        self.pdf_converter = PDFConverter()
        self.photo_detector = PhotoDetector()
        self.signature_detector = SignatureDetector()
        self.template_engine = TemplateEngine()
        self.file_manager = FileManager()

        # Load templates at initialization.
        self.template_engine.load_templates()

        logger.info("ProcessingService initialized")

    def extract(
        self,
        pdf_bytes: bytes,
        request_id: Optional[str] = None,
    ) -> Dict:
        """
        Extract photo and signature from a scanned PDF.

        Args:
            pdf_bytes: Raw PDF content.
            request_id: Optional pre-generated request ID.

        Returns:
            Dict with extraction results including paths and metadata.
        """
        start_time = time.perf_counter()
        request_id = request_id or FileManager.generate_request_id()
        request_dir = self.file_manager.create_request_dir(request_id)

        try:
            # Step 1: Convert PDF to page images.
            logger.info("[%s] Converting PDF to images...", request_id[:8])
            page_images = self.pdf_converter.pdf_to_images_from_bytes(pdf_bytes)
            logger.info(
                "[%s] Converted %d pages", request_id[:8], len(page_images)
            )

            # Step 2: Detect and extract photo.
            logger.info("[%s] Detecting photo...", request_id[:8])
            photo_path = self.file_manager.get_photo_path(request_dir)
            photo_result = self.photo_detector.detect_and_extract(
                page_images, photo_path
            )

            # Step 3: Detect and extract signature.
            logger.info("[%s] Detecting signature...", request_id[:8])
            sig_path = self.file_manager.get_signature_path(request_dir)
            sig_result = self.signature_detector.detect_and_extract(
                page_images, sig_path
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            result = {
                "request_id": request_id,
                "photo": self._format_detection(photo_result, photo_path),
                "signature": self._format_detection(sig_result, sig_path),
                "processing_time_ms": round(elapsed_ms, 1),
            }

            logger.info(
                "[%s] Extraction complete in %.1fms — photo: %s, signature: %s",
                request_id[:8],
                elapsed_ms,
                "found" if photo_result else "NOT FOUND",
                "found" if sig_result else "NOT FOUND",
            )

            return result

        except Exception as e:
            logger.error(
                "[%s] Extraction failed: %s", request_id[:8], e, exc_info=True
            )
            # Clean up on failure.
            self.file_manager.cleanup_request(request_dir)
            raise

    def process(
        self,
        source_pdf_bytes: bytes,
        template_name: str,
        form_pdf_bytes: Optional[bytes] = None,
        form_pdf_path: Optional[Path] = None,
        request_id: Optional[str] = None,
        custom_coords: Optional[Dict[str, Dict]] = None,
    ) -> Tuple[Path, Dict]:
        """
        Full pipeline: extract photo/signature → fill form → generate PDF.

        Either form_pdf_bytes or form_pdf_path must be provided.

        Args:
            source_pdf_bytes: The scanned documents PDF.
            template_name: Template name for field placement.
            form_pdf_bytes: Optional raw bytes of the blank form PDF.
            form_pdf_path: Optional path to a pre-stored blank form PDF.
            request_id: Optional pre-generated request ID.
            custom_coords: Optional custom field coordinates to override template

        Returns:
            Tuple of (output_path, extraction_results_dict).

        Raises:
            ValueError: If template not found or no form PDF provided.
        """
        from app.models.template import FieldPlacement
        
        start_time = time.perf_counter()
        request_id = request_id or FileManager.generate_request_id()

        # Validate template exists before doing any work.
        template = self.template_engine.get_template(template_name)
        if template is None:
            available = self.template_engine.list_templates()
            raise ValueError(
                f"Template '{template_name}' not found. "
                f"Available: {', '.join(available) or '(none)'}"
            )

        # Step 1: Extract photo and signature.
        extract_result = self.extract(source_pdf_bytes, request_id)
        request_dir = self.file_manager.extracted_dir / request_id

        # Step 2: Prepare image paths for form filling.
        images: Dict[str, Path] = {}

        if extract_result["photo"]["found"]:
            photo_path = Path(extract_result["photo"]["path"])
            if photo_path.exists():
                images["photo"] = photo_path

        if extract_result["signature"]["found"]:
            sig_path = Path(extract_result["signature"]["path"])
            if sig_path.exists():
                images["signature"] = sig_path

        if not images:
            logger.warning(
                "[%s] No images extracted — form will have empty fields",
                request_id[:8],
            )

        # Step 3: Convert custom coords dict to FieldPlacement objects
        parsed_custom_coords = None
        if custom_coords:
            parsed_custom_coords = {}
            for field_name, coords in custom_coords.items():
                parsed_custom_coords[field_name] = FieldPlacement(**coords)

        # Step 4: Fill the form.
        output_path = self.file_manager.get_output_path(
            request_id, template_name
        )

        if form_pdf_bytes:
            self.template_engine.fill_form_from_bytes(
                template_name=template_name,
                form_pdf_bytes=form_pdf_bytes,
                images=images,
                output_path=output_path,
                custom_coords=parsed_custom_coords,
            )
        elif form_pdf_path and form_pdf_path.exists():
            self.template_engine.fill_form(
                template_name=template_name,
                form_pdf_path=form_pdf_path,
                images=images,
                output_path=output_path,
                custom_coords=parsed_custom_coords,
            )
        else:
            raise ValueError(
                "No form PDF provided. Supply either form_pdf_bytes or "
                "form_pdf_path."
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "[%s] Process complete in %.1fms — output: %s",
            request_id[:8],
            elapsed_ms,
            output_path,
        )

        extract_result["processing_time_ms"] = round(elapsed_ms, 1)
        extract_result["output_path"] = str(output_path)

        return output_path, extract_result

    def _format_detection(
        self,
        result: Optional[DetectionResult],
        expected_path: Path,
    ) -> Dict:
        """Format a DetectionResult into a serializable dict."""
        if result is None:
            return {
                "found": False,
                "confidence": 0.0,
                "page": -1,
                "bbox": None,
                "path": None,
                "strategy": None,
            }

        return {
            "found": True,
            "confidence": round(result.confidence, 3),
            "page": result.page_index,
            "bbox": list(result.bbox),
            "path": str(expected_path),
            "strategy": result.strategy_name,
        }

    def cleanup_old_files(self) -> int:
        """Run TTL-based cleanup. Returns number of directories removed."""
        return self.file_manager.cleanup_old_files()

    def get_available_strategies(self) -> Dict[str, list]:
        """Return available detection strategies."""
        return {
            "photo": self.photo_detector.get_available_strategies(),
            "signature": [self.signature_detector.strategy_name],
        }
