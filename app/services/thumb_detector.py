"""
Thumb impression detection service — orchestrates thumb detection strategies.

Scans all PDF pages (focusing on lower portions) to find the most likely
thumb impression using contour analysis and heuristic scoring.
"""

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import settings
from app.strategies.base import DetectionResult, SignatureDetectionStrategy
from app.strategies.thumb_contour_strategy import ThumbContourStrategy
from app.utils.image_processing import crop_region, save_image

logger = logging.getLogger(__name__)


class ThumbDetector:
    """
    Orchestrates thumb impression detection across multiple PDF pages.

    Currently uses ThumbContourStrategy. The architecture supports
    adding other strategies in the future as drop-in replacements.

    Usage:
        detector = ThumbDetector()
        result = detector.detect_and_extract(page_images, output_path)
    """

    def __init__(
        self,
        strategy: Optional[SignatureDetectionStrategy] = None,
    ) -> None:
        """
        Args:
            strategy: Override the default detection strategy.
                      If None, uses ThumbContourStrategy.
        """
        self._strategy = strategy or ThumbContourStrategy()
        logger.info(
            "ThumbDetector initialized (strategy=%s)",
            self._strategy.name,
        )

    def detect_in_page(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect thumb impression candidates in a single page.

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
        Search all PDF pages for the best thumb impression candidate.

        Strategy:
        - Scan pages in reverse order (thumb impression is more likely on later pages)
        - Collect all candidates from all pages
        - Apply cross-page scoring adjustments
        - Return the highest-scoring candidate

        Args:
            page_images: List of (page_index, image) tuples.

        Returns:
            Best thumb impression detection, or None if nothing found.
        """
        all_candidates: List[DetectionResult] = []
        total_pages = len(page_images)

        for page_idx, image in page_images:
            candidates = self.detect_in_page(image, page_idx)
            all_candidates.extend(candidates)

        if not all_candidates:
            logger.warning(
                "No thumb impression candidates found across %d pages",
                total_pages,
            )
            return None

        # Apply cross-page scoring: prefer thumb impressions on later pages.
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
        is_low_confidence = best.confidence < settings.THUMB_CONFIDENCE_THRESHOLD

        logger.info(
            "Best thumb impression candidate: page %d, bbox=%s, confidence=%.2f%s",
            best.page_index,
            best.bbox,
            best.confidence,
            " [LOW CONFIDENCE]" if is_low_confidence else "",
        )
        
        if is_low_confidence:
            logger.warning("Rejecting thumb impression candidate due to low confidence")
            return None

        return best

    def detect_and_extract(
        self,
        page_images: List[tuple[int, np.ndarray]],
        output_path: Path,
    ) -> Optional[DetectionResult]:
        """
        Full pipeline: detect the best thumb impression, crop, and save as PNG.

        Args:
            page_images: List of (page_index, image) tuples.
            output_path: Where to save the extracted thumb impression.

        Returns:
            DetectionResult, or None if no thumb impression found.
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

        # Crop the thumb impression region.
        thumb = crop_region(source_image, best.bbox)

        # Save the cropped thumb impression.
        save_image(thumb, output_path)

        # Update metadata with save path.
        best.metadata["saved_to"] = str(output_path)

        return best

    @property
    def strategy_name(self) -> str:
        """Return the name of the current detection strategy."""
        return self._strategy.name
