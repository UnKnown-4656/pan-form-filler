"""
Photo detection service — orchestrates face detection strategies.

Implements the dual-strategy approach:
1. Try Haar Cascade first (fast path)
2. Fall back to DNN if Haar finds nothing or has low confidence
3. Select the best face detection
4. Expand bounding box to passport photo dimensions
5. Crop and save the photo

The strategy used is configurable: 'haar', 'dnn', or 'auto' (default).
"""

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import settings
from app.strategies.base import DetectionResult, PhotoDetectionStrategy
from app.strategies.dnn_strategy import DNNStrategy
from app.strategies.haar_strategy import HaarStrategy
from app.utils.image_processing import (
    BBox,
    crop_region,
    expand_bbox,
    save_image,
)

logger = logging.getLogger(__name__)


class PhotoDetector:
    """
    Orchestrates photo detection across multiple PDF pages using
    configurable detection strategies.

    Usage:
        detector = PhotoDetector()
        result = detector.detect_and_extract(page_images, output_path)
    """

    def __init__(self, strategy: Optional[str] = None) -> None:
        """
        Args:
            strategy: Detection strategy to use.
                      'haar'  — Haar Cascade only
                      'dnn'   — DNN only
                      'auto'  — Haar first, DNN fallback (default)
        """
        self._strategy_name = strategy or settings.PHOTO_DETECTION_STRATEGY
        self._haar = HaarStrategy()
        self._dnn = DNNStrategy()

        logger.info("PhotoDetector initialized (strategy=%s)", self._strategy_name)

    def detect_in_page(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect faces in a single page image using the configured strategy.

        Args:
            image: BGR page image.
            page_index: Zero-based page index.

        Returns:
            List of detections sorted by confidence.
        """
        if self._strategy_name == "haar":
            return self._haar.detect(image, page_index)
        elif self._strategy_name == "dnn":
            return self._dnn.detect(image, page_index)
        elif self._strategy_name == "auto":
            return self._auto_detect(image, page_index)
        else:
            logger.warning(
                "Unknown strategy '%s', falling back to 'auto'",
                self._strategy_name,
            )
            return self._auto_detect(image, page_index)

    def _auto_detect(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Dual-strategy detection: Haar first, DNN fallback.

        Falls back to DNN if:
        - Haar finds nothing
        - Haar's best confidence is below 0.3 (unreliable)
        """
        # Fast path: try Haar first.
        haar_results = self._haar.detect(image, page_index)

        if haar_results and haar_results[0].confidence >= 0.3:
            logger.debug(
                "Auto: Haar succeeded on page %d (confidence=%.2f)",
                page_index,
                haar_results[0].confidence,
            )
            return haar_results

        # Slow path: fall back to DNN.
        if self._dnn.is_available():
            logger.info(
                "Auto: Haar insufficient on page %d, trying DNN...",
                page_index,
            )
            dnn_results = self._dnn.detect(image, page_index)

            if dnn_results:
                return dnn_results

            # If DNN also found nothing but Haar had something, use Haar's results.
            if haar_results:
                logger.info(
                    "Auto: DNN found nothing, using Haar results on page %d",
                    page_index,
                )
                return haar_results
        else:
            logger.warning("Auto: DNN not available, using Haar results only")
            return haar_results

        return []

    def detect_across_pages(
        self,
        page_images: List[tuple[int, np.ndarray]],
    ) -> Optional[DetectionResult]:
        """
        Search all PDF pages for the best passport photo.

        Strategy:
        - Run detection on every page
        - Collect all faces found
        - Select the one with the largest area (passport photo is bigger
          than ID card photos embedded in documents)
        - If areas are similar, prefer the one with higher confidence

        Args:
            page_images: List of (page_index, image) tuples from PDFConverter.

        Returns:
            The best detection result, or None if no face was found.
        """
        all_detections: List[DetectionResult] = []

        for page_idx, image in page_images:
            detections = self.detect_in_page(image, page_idx)
            all_detections.extend(detections)

        if not all_detections:
            logger.warning("No faces detected across %d pages", len(page_images))
            return None

        # Sort by area (largest first), then by confidence as tiebreaker.
        all_detections.sort(
            key=lambda d: (d.area, d.confidence),
            reverse=True,
        )

        best = all_detections[0]
        logger.info(
            "Best photo detection: page %d, bbox=%s, area=%d, confidence=%.2f, "
            "strategy=%s",
            best.page_index,
            best.bbox,
            best.area,
            best.confidence,
            best.strategy_name,
        )
        return best

    def detect_and_extract(
        self,
        page_images: List[tuple[int, np.ndarray]],
        output_path: Path,
    ) -> Optional[DetectionResult]:
        """
        Full pipeline: detect the best face, expand to passport photo
        dimensions, crop, and save as PNG.

        Args:
            page_images: List of (page_index, image) tuples.
            output_path: Where to save the extracted photo.

        Returns:
            DetectionResult with the expanded bbox, or None if no face found.
        """
        best_detection = self.detect_across_pages(page_images)

        if best_detection is None:
            return None

        # Find the source image for the detected page.
        source_image: Optional[np.ndarray] = None
        for page_idx, image in page_images:
            if page_idx == best_detection.page_index:
                source_image = image
                break

        if source_image is None:
            logger.error("Source image for page %d not found", best_detection.page_index)
            return None

        # Expand face bounding box to include full passport photo area.
        expanded_bbox = expand_bbox(
            best_detection.bbox,
            source_image.shape[:2],
            expand_top=settings.PHOTO_EXPAND_TOP,
            expand_bottom=settings.PHOTO_EXPAND_BOTTOM,
            expand_sides=settings.PHOTO_EXPAND_SIDES,
        )

        # Crop the expanded region.
        photo = crop_region(source_image, expanded_bbox)

        # Save the extracted photo.
        save_image(photo, output_path)

        # Return updated detection with expanded bbox.
        return DetectionResult(
            bbox=expanded_bbox,
            confidence=best_detection.confidence,
            page_index=best_detection.page_index,
            detection_type=best_detection.detection_type,
            strategy_name=best_detection.strategy_name,
            metadata={
                **best_detection.metadata,
                "original_face_bbox": best_detection.bbox,
                "expanded_to_photo": True,
                "saved_to": str(output_path),
            },
        )

    def get_available_strategies(self) -> List[str]:
        """Return names of strategies that are currently available."""
        available = []
        if self._haar.is_available():
            available.append(self._haar.name)
        if self._dnn.is_available():
            available.append(self._dnn.name)
        return available
