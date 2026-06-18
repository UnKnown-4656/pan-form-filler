"""
Contour-based signature detection strategy.

Uses classical image processing (no ML) to detect handwritten signatures:
1. Focus on the lower portion of each page
2. Adaptive thresholding
3. Morphological cleanup
4. Contour analysis with heuristic filtering
5. Multi-factor scoring

This is the V1 approach. V2 will add a YOLO-based strategy as an alternative.
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
class _ContourCandidate:
    """Internal scoring data for a contour candidate."""
    contour: np.ndarray
    bbox: tuple[int, int, int, int]
    area: float
    aspect_ratio: float
    solidity: float
    density: float
    vertical_position: float  # 0.0 = top, 1.0 = bottom of ROI
    score: float = 0.0


class ContourStrategy(SignatureDetectionStrategy):
    """
    Heuristic contour-based signature detection.

    The core insight: handwritten signatures have distinctive geometric
    properties that distinguish them from printed text, QR codes, logos,
    and table borders:

    - Moderate aspect ratio (wider than tall, but not a line)
    - Low solidity (irregular shape, not a filled rectangle)
    - Low-to-moderate stroke density (sparse, not a text block)
    - Typically found in the lower half of a page
    - Connected but irregular strokes

    Expected accuracy: ~75–85% on clean scans, ~60–70% on noisy scans.
    """

    def detect(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect signature candidates in a page image.

        Returns candidates sorted by score (best first).
        """
        img_h, img_w = image.shape[:2]

        # Step 1: Focus on lower portion of the page.
        focus_ratio = settings.SIG_FOCUS_LOWER_PERCENT
        roi_y_start = int(img_h * (1.0 - focus_ratio))
        roi = image[roi_y_start:, :]
        roi_h, roi_w = roi.shape[:2]

        logger.debug(
            "Signature ROI: page %d, y=%d→%d (%dx%d)",
            page_index, roi_y_start, img_h, roi_w, roi_h,
        )

        # Step 2: Preprocess — grayscale + adaptive threshold.
        gray = to_grayscale(roi)
        binary = adaptive_threshold(
            gray,
            block_size=settings.SIG_ADAPTIVE_BLOCK_SIZE,
            c_value=settings.SIG_ADAPTIVE_C,
        )

        # Step 3: Morphological close to connect broken signature strokes.
        binary = morphological_close(
            binary, kernel_size=settings.SIG_MORPH_KERNEL_SIZE
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
                    detection_type=DetectionType.SIGNATURE,
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
                "Contour: Found %d signature candidate(s) on page %d "
                "(best score: %.2f)",
                len(results),
                page_index,
                results[0].confidence,
            )
        else:
            logger.debug(
                "Contour: No signature candidates on page %d", page_index
            )

        return results

    def _analyze_contours(
        self,
        contours: List[np.ndarray],
        binary: np.ndarray,
        roi_w: int,
        roi_h: int,
    ) -> List[_ContourCandidate]:
        """
        Filter contours through heuristic rules and score survivors.

        Filtering order is from cheapest to most expensive computation.
        """
        candidates: List[_ContourCandidate] = []

        for contour in contours:
            # --- Bounding box ---
            x, y, w, h = cv2.boundingRect(contour)

            # Filter 1: Minimum size (reject noise/dots).
            if w < settings.SIG_MIN_WIDTH or h < settings.SIG_MIN_HEIGHT:
                continue

            # Filter 2: Maximum width (reject full-width text blocks/tables).
            if w > roi_w * settings.SIG_MAX_WIDTH_RATIO:
                continue
                
            # Filter 2.1: Maximum height (reject tall things like photos/fingerprints)
            if h > roi_h * settings.SIG_MAX_HEIGHT_RATIO:
                continue

            # Filter 3: Aspect ratio (signatures are wider than tall).
            if h == 0:
                continue
            aspect_ratio = w / h

            if aspect_ratio < settings.SIG_ASPECT_RATIO_MIN:
                continue  # Too square — likely stamp, logo, QR code
            if aspect_ratio > settings.SIG_ASPECT_RATIO_MAX:
                continue  # Too elongated — likely a horizontal line/rule

            # Filter 4: Solidity (reject filled rectangles and QR codes).
            sol = contour_solidity(contour)
            if sol > settings.SIG_SOLIDITY_MAX:
                continue  # Too solid — likely a printed block

            # Filter 5: Stroke density (reject dense text blocks).
            # Extract the ROI from the binary image for density calculation.
            binary_roi = binary[y:y + h, x:x + w]
            density = stroke_density(binary_roi)
            if density > settings.SIG_DENSITY_MAX:
                continue  # Too dense — likely printed text

            # Filter 6: Minimum density (reject nearly empty regions).
            if density < 0.02:
                continue  # Too sparse — likely scanner artifact

            # --- Compute area and vertical position ---
            area = cv2.contourArea(contour)
            vertical_position = (y + h / 2) / roi_h  # 0=top, 1=bottom

            candidates.append(
                _ContourCandidate(
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

    def _score_candidate(self, candidate: _ContourCandidate) -> float:
        """
        Multi-factor scoring for signature likelihood.

        Each factor contributes a weighted score. Total is normalized to [0, 1].

        Scoring rationale:
        - Position: Signatures are usually near the bottom of a page.
        - Aspect ratio: 2.0–5.0 is the sweet spot for signatures.
        - Density: 0.05–0.25 is typical for handwriting.
        - Solidity: 0.15–0.55 indicates irregular, handwritten strokes.
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
        # Sweet spot: 2.0–5.0
        weight = 0.25
        max_score += weight
        ar = candidate.aspect_ratio
        if 2.0 <= ar <= 5.0:
            score += weight * 1.0
        elif 1.5 <= ar < 2.0 or 5.0 < ar <= 6.0:
            score += weight * 0.6
        else:
            score += weight * 0.2

        # --- Factor 3: Stroke density (weight: 0.20) ---
        # Sweet spot: 0.05–0.25
        weight = 0.20
        max_score += weight
        d = candidate.density
        if 0.05 <= d <= 0.25:
            score += weight * 1.0
        elif 0.02 <= d < 0.05 or 0.25 < d <= 0.35:
            score += weight * 0.5
        else:
            score += weight * 0.1

        # --- Factor 4: Solidity (weight: 0.20) ---
        # Sweet spot: 0.15–0.55 (irregular handwriting)
        weight = 0.20
        max_score += weight
        s = candidate.solidity
        if 0.15 <= s <= 0.55:
            score += weight * 1.0
        elif 0.10 <= s < 0.15 or 0.55 < s <= 0.65:
            score += weight * 0.5
        else:
            score += weight * 0.1

        # --- Factor 5: Area bonus (weight: 0.10) ---
        # Moderate area preferred (not tiny, not huge).
        weight = 0.10
        max_score += weight
        area_ratio = candidate.area / (candidate.bbox[2] * candidate.bbox[3])
        if 0.1 <= area_ratio <= 0.6:
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
        return "contour_analysis"
