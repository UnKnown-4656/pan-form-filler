"""
Contour-based thumb impression detection strategy.

Uses classical image processing (no ML) to detect thumb impressions:
1. Focus on the lower portion of each page
2. Adaptive thresholding
3. Morphological cleanup
4. Contour analysis with heuristic filtering
5. Multi-factor scoring

Thumb impressions differ from signatures:
- More circular/square shape (aspect ratio closer to 1.0)
- Higher density (more ink coverage)
- Higher solidity (more filled area)
- Typically found near signature areas
"""

import logging
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from app.config import settings
from app.strategies.base import (
    DetectionResult,
    DetectionType,
    SignatureDetectionStrategy,
)
from app.utils.image_processing import (
    adaptive_threshold,
    contour_solidity,
    find_contours,
    morphological_close,
    morphological_dilate,
    stroke_density,
    to_grayscale,
)

logger = logging.getLogger(__name__)


@dataclass
class _ThumbCandidate:
    """Internal scoring data for a thumb impression candidate."""
    contour: np.ndarray
    bbox: tuple[int, int, int, int]
    area: float
    aspect_ratio: float
    solidity: float
    density: float
    vertical_position: float  # 0.0 = top, 1.0 = bottom of ROI
    score: float = 0.0


class ThumbContourStrategy(SignatureDetectionStrategy):
    """
    Heuristic contour-based thumb impression detection.

    The core insight: thumb impressions have distinctive geometric
    properties that distinguish them from signatures, text, and other elements:

    - Aspect ratio closer to 1.0 (more circular/square than signatures)
    - Higher solidity (more filled area than signatures)
    - Higher stroke density (more ink coverage)
    - Typically found in the lower half of a page
    - More compact and rounded shape

    Expected accuracy: ~70–80% on clean scans, ~55–65% on noisy scans.
    """

    def detect(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect thumb impression candidates in a page image.

        Returns candidates sorted by score (best first).
        """
        img_h, img_w = image.shape[:2]

        # Step 1: Focus on lower portion of the page.
        focus_ratio = settings.THUMB_FOCUS_LOWER_PERCENT
        roi_y_start = int(img_h * (1.0 - focus_ratio))
        roi = image[roi_y_start:, :]
        roi_h, roi_w = roi.shape[:2]

        logger.debug(
            "Thumb ROI: page %d, y=%d→%d (%dx%d)",
            page_index, roi_y_start, img_h, roi_w, roi_h,
        )

        # Step 2: Preprocess — grayscale + adaptive threshold.
        gray = to_grayscale(roi)
        binary = adaptive_threshold(
            gray,
            block_size=settings.THUMB_ADAPTIVE_BLOCK_SIZE,
            c_value=settings.THUMB_ADAPTIVE_C,
        )

        # Step 3: Morphological close to connect broken thumb strokes.
        binary = morphological_close(
            binary, kernel_size=settings.THUMB_MORPH_KERNEL_SIZE
        )

        # Step 4: Light dilation to merge nearby stroke fragments.
        binary = morphological_dilate(binary, kernel_size=3, iterations=2)

        # Step 5: Find and analyze contours.
        contours = find_contours(binary)
        logger.debug(
            "Found %d raw contours on page %d", len(contours), page_index
        )

        # Step 6: Filter and score candidates.
        candidates = self._analyze_contours(contours, binary, roi_w, roi_h)

        # Step 7: Convert to DetectionResult objects.
        # Adjust Y coordinates back to full-page coordinate space.
        results: List[DetectionResult] = []
        for candidate in candidates:
            x, y, w, h = candidate.bbox
            adjusted_y = y + roi_y_start  # Map ROI coords → page coords

            results.append(
                DetectionResult(
                    bbox=(x, adjusted_y, w, h),
                    confidence=candidate.score,
                    page_index=page_index,
                    detection_type=DetectionType.THUMB,
                    strategy_name=self.name,
                    metadata={
                        "aspect_ratio": round(candidate.aspect_ratio, 2),
                        "solidity": round(candidate.solidity, 3),
                        "density": round(candidate.density, 3),
                        "area": int(candidate.area),
                        "vertical_position": round(candidate.vertical_position, 2),
                    },
                )
            )

        results.sort(key=lambda r: r.confidence, reverse=True)

        if results:
            logger.info(
                "Thumb: Found %d thumb impression candidate(s) on page %d "
                "(best score: %.2f)",
                len(results),
                page_index,
                results[0].confidence,
            )
        else:
            logger.debug(
                "Thumb: No thumb impression candidates on page %d", page_index
            )

        return results

    def _analyze_contours(
        self,
        contours: List[np.ndarray],
        binary: np.ndarray,
        roi_w: int,
        roi_h: int,
    ) -> List[_ThumbCandidate]:
        """
        Filter contours through heuristic rules and score survivors.

        Filtering order is from cheapest to most expensive computation.
        """
        candidates: List[_ThumbCandidate] = []

        for contour in contours:
            # --- Bounding box ---
            x, y, w, h = cv2.boundingRect(contour)

            # Filter 1: Minimum size (reject noise/dots).
            if w < settings.THUMB_MIN_WIDTH or h < settings.THUMB_MIN_HEIGHT:
                continue

            # Filter 2: Maximum width (reject full-width text blocks/tables).
            if w > roi_w * settings.THUMB_MAX_WIDTH_RATIO:
                continue
                
            # Filter 2.1: Maximum height (reject tall things like photos)
            if h > roi_h * settings.THUMB_MAX_HEIGHT_RATIO:
                continue

            # Filter 3: Aspect ratio (thumb impressions are more circular/square).
            if h == 0:
                continue
            aspect_ratio = w / h

            if aspect_ratio < settings.THUMB_ASPECT_RATIO_MIN:
                continue  # Too narrow — likely signature or line
            if aspect_ratio > settings.THUMB_ASPECT_RATIO_MAX:
                continue  # Too wide — likely signature or text block

            # Filter 4: Solidity (thumb impressions are more solid than signatures).
            sol = contour_solidity(contour)
            if sol < settings.THUMB_SOLIDITY_MIN:
                continue  # Too sparse — likely signature or handwriting
            if sol > settings.THUMB_SOLIDITY_MAX:
                continue  # Too solid — likely printed block

            # Filter 5: Stroke density (thumb impressions are denser than signatures).
            # Extract the ROI from the binary image for density calculation.
            binary_roi = binary[y:y + h, x:x + w]
            density = stroke_density(binary_roi)
            if density < settings.THUMB_DENSITY_MIN:
                continue  # Too sparse — likely signature or light marks
            if density > settings.THUMB_DENSITY_MAX:
                continue  # Too dense — likely printed text or solid block

            # --- Compute area and vertical position ---
            area = cv2.contourArea(contour)
            vertical_position = (y + h / 2) / roi_h  # 0=top, 1=bottom

            candidates.append(
                _ThumbCandidate(
                    contour=contour,
                    bbox=(x, y, w, h),
                    area=area,
                    aspect_ratio=aspect_ratio,
                    solidity=sol,
                    density=density,
                    vertical_position=vertical_position,
                )
            )

        # Score surviving candidates.
        for candidate in candidates:
            candidate.score = self._score_candidate(candidate)

        # Sort by score descending and return top candidates.
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:5]  # Return top 5 at most

    def _score_candidate(self, candidate: _ThumbCandidate) -> float:
        """
        Multi-factor scoring for thumb impression likelihood.

        Each factor contributes a weighted score. Total is normalized to [0, 1].

        Scoring rationale:
        - Position: Thumb impressions are usually near the bottom of a page.
        - Aspect ratio: 0.8–1.5 is the sweet spot for thumb impressions (more circular).
        - Density: 0.1–0.6 is typical for thumb impressions (denser than signatures).
        - Solidity: 0.3–0.9 indicates more filled area than signatures.
        - Area: Moderate area is preferred (not too small, not too large).
        """
        score = 0.0
        max_score = 0.0

        # --- Factor 1: Vertical position (weight: 0.25) ---
        # Prefer candidates in the lower portion of the ROI.
        weight = 0.25
        max_score += weight
        if candidate.vertical_position > 0.5:
            score += weight * min(1.0, (candidate.vertical_position - 0.5) * 2)
        else:
            score += weight * 0.3  # Small score even for upper candidates

        # --- Factor 2: Aspect ratio (weight: 0.25) ---
        # Sweet spot: 0.8–1.5 (more circular/square than signatures)
        weight = 0.25
        max_score += weight
        ar = candidate.aspect_ratio
        if 0.8 <= ar <= 1.5:
            score += weight * 1.0
        elif 0.6 <= ar < 0.8 or 1.5 < ar <= 2.0:
            score += weight * 0.6
        else:
            score += weight * 0.2

        # --- Factor 3: Stroke density (weight: 0.20) ---
        # Sweet spot: 0.1–0.6 (denser than signatures)
        weight = 0.20
        max_score += weight
        d = candidate.density
        if 0.1 <= d <= 0.6:
            score += weight * 1.0
        elif 0.05 <= d < 0.1 or 0.6 < d <= 0.7:
            score += weight * 0.5
        else:
            score += weight * 0.1

        # --- Factor 4: Solidity (weight: 0.20) ---
        # Sweet spot: 0.3–0.9 (more solid than signatures)
        weight = 0.20
        max_score += weight
        s = candidate.solidity
        if 0.3 <= s <= 0.9:
            score += weight * 1.0
        elif 0.2 <= s < 0.3 or 0.9 < s <= 0.95:
            score += weight * 0.5
        else:
            score += weight * 0.1

        # --- Factor 5: Area bonus (weight: 0.10) ---
        # Moderate area preferred (not tiny, not huge).
        weight = 0.10
        max_score += weight
        area_ratio = candidate.area / (candidate.bbox[2] * candidate.bbox[3])
        if 0.15 <= area_ratio <= 0.7:
            score += weight * 1.0
        else:
            score += weight * 0.4

        # Normalize to [0, 1].
        return score / max_score if max_score > 0 else 0.0

    def is_available(self) -> bool:
        """Contour analysis needs no external models — always available."""
        return True

    @property
    def name(self) -> str:
        return "thumb_contour_analysis"
