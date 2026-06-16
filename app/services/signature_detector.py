"""
Signature detection service — orchestrates signature detection strategies.

Scans all PDF pages (focusing on lower portions) to find the most likely
handwritten signature using contour analysis and heuristic scoring.
"""

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import settings
from app.strategies.base import DetectionResult, SignatureDetectionStrategy
from app.strategies.contour_strategy import ContourStrategy
from app.utils.image_processing import crop_region, save_image

logger = logging.getLogger(__name__)


class SignatureDetector:
    """
    Orchestrates signature detection across multiple PDF pages.

    Currently uses ContourStrategy (V1). The architecture supports
    adding YOLO-based detection in V2 as a drop-in replacement.

    Usage:
        detector = SignatureDetector()
        result = detector.detect_and_extract(page_images, output_path)
    """

    def __init__(
        self,
        strategy: Optional[SignatureDetectionStrategy] = None,
    ) -> None:
        """
        Args:
            strategy: Override the default detection strategy.
                      If None, uses ContourStrategy.
        """
        self._strategy = strategy or ContourStrategy()
        logger.info(
            "SignatureDetector initialized (strategy=%s)",
            self._strategy.name,
        )

    def detect_in_page(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect signature candidates in a single page.

        Args:
            image: BGR page image.
            page_index: Zero-based page index.

        Returns:
            List of detection results sorted by score.
        """
        return self._strategy.detect(image, page_index)

    def detect_across_pages(
        self,
        page_images: List[tuple[int, np.ndarray]],
    ) -> Optional[DetectionResult]:
        """
        Search all PDF pages for the best signature candidate.

        Strategy:
        - Scan pages in reverse order (signature is more likely on later pages)
        - Collect all candidates from all pages
        - Apply cross-page scoring adjustments
        - Return the highest-scoring candidate

        Args:
            page_images: List of (page_index, image) tuples.

        Returns:
            Best signature detection, or None if nothing found.
        """
        all_candidates: List[DetectionResult] = []
        total_pages = len(page_images)

        for page_idx, image in page_images:
            candidates = self.detect_in_page(image, page_idx)
            all_candidates.extend(candidates)

        if not all_candidates:
            logger.warning(
                "No signature candidates found across %d pages",
                total_pages,
            )
            return None

        # Apply cross-page scoring: prefer signatures on later pages.
        # In CSC workflows, the signature is usually on the last page or
        # on the application form (which is often page 0 or the last page).
        for candidate in all_candidates:
            page_bonus = 0.0
            if total_pages > 1:
                # Later pages get a small bonus.
                page_position = candidate.page_index / (total_pages - 1)
                page_bonus = page_position * 0.1  # Up to 10% bonus

            # Adjust confidence with page bonus (cap at 1.0).
            adjusted = min(1.0, candidate.confidence + page_bonus)
            candidate.confidence = adjusted

        # Sort by adjusted confidence.
        all_candidates.sort(key=lambda c: c.confidence, reverse=True)

        best = all_candidates[0]
        is_low_confidence = best.confidence < settings.SIG_CONFIDENCE_THRESHOLD

        logger.info(
            "Best signature candidate: page %d, bbox=%s, confidence=%.2f%s",
            best.page_index,
            best.bbox,
            best.confidence,
            " [LOW CONFIDENCE]" if is_low_confidence else "",
        )

        return best

    def detect_and_extract(
        self,
        page_images: List[tuple[int, np.ndarray]],
        output_path: Path,
    ) -> Optional[DetectionResult]:
        """
        Full pipeline: detect the best signature, crop, and save as PNG.

        Args:
            page_images: List of (page_index, image) tuples.
            output_path: Where to save the extracted signature.

        Returns:
            DetectionResult, or None if no signature found.
        """
        best = self.detect_across_pages(page_images)

        if best is None:
            return None

        # Find the source image.
        source_image: Optional[np.ndarray] = None
        for page_idx, image in page_images:
            if page_idx == best.page_index:
                source_image = image
                break

        if source_image is None:
            logger.error(
                "Source image for page %d not found", best.page_index
            )
            return None

        # Crop the signature region.
        signature = crop_region(source_image, best.bbox)

        # Save the cropped signature.
        save_image(signature, output_path)

        # Update metadata with save path.
        best.metadata["saved_to"] = str(output_path)

        return best

    @property
    def strategy_name(self) -> str:
        """Return the name of the current detection strategy."""
        return self._strategy.name
