"""
Haar Cascade face detection strategy.

Fast, lightweight face detection using OpenCV's pre-trained Haar Cascade
classifier. Best for well-lit, frontal passport photos.

Performance: ~10–30ms per page on modern hardware.
Accuracy: ~75% (frontal faces in good lighting).
"""

import logging
from typing import List

import cv2
import numpy as np

from app.config import settings
from app.strategies.base import DetectionResult, DetectionType, PhotoDetectionStrategy
from app.utils.image_processing import to_grayscale, enhance_contrast

logger = logging.getLogger(__name__)


class HaarStrategy(PhotoDetectionStrategy):
    """
    Haar Cascade face detection.

    Uses OpenCV's pre-trained frontal face cascade. The cascade file
    ships with opencv-python-headless — no additional download needed.

    Pros:
    - Extremely fast on CPU
    - Zero additional dependencies
    - Works well for frontal passport photos

    Cons:
    - Poor accuracy for tilted/rotated faces
    - High false positive rate in cluttered documents
    - Sensitive to lighting conditions
    """

    def __init__(self) -> None:
        self._cascade: cv2.CascadeClassifier | None = None
        self._loaded = False

    def _load_cascade(self) -> None:
        """Lazy-load the Haar Cascade classifier."""
        if self._loaded:
            return

        # Try project-local model first, then OpenCV's bundled data.
        local_path = settings.MODELS_DIR / "haarcascade_frontalface_default.xml"

        if local_path.exists():
            cascade_path = str(local_path)
            logger.info("Loading Haar Cascade from local: %s", cascade_path)
        else:
            # Fall back to OpenCV's bundled cascade file.
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            logger.info("Loading Haar Cascade from OpenCV data: %s", cascade_path)

        self._cascade = cv2.CascadeClassifier(cascade_path)

        if self._cascade.empty():
            logger.error("Failed to load Haar Cascade from: %s", cascade_path)
            self._loaded = False
            return

        self._loaded = True
        logger.info("Haar Cascade loaded successfully")

    def detect(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect faces using Haar Cascade.

        Applies CLAHE enhancement before detection to handle shadows
        from pasted passport photos.
        """
        self._load_cascade()

        if not self._loaded or self._cascade is None:
            logger.warning("Haar Cascade not available, returning empty results")
            return []

        # Enhance contrast to handle scanner shadows, then convert to grayscale.
        enhanced = enhance_contrast(image)
        gray = to_grayscale(enhanced)

        # Run cascade detection.
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=settings.HAAR_SCALE_FACTOR,
            minNeighbors=settings.HAAR_MIN_NEIGHBORS,
            minSize=settings.haar_min_size,
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        results: List[DetectionResult] = []

        if len(faces) == 0:
            logger.debug("Haar: No faces found on page %d", page_index)
            return results

        for i, (x, y, w, h) in enumerate(faces):
            # Haar doesn't provide a confidence score, so we use a heuristic:
            # larger faces relative to the image are more likely to be the
            # passport photo (ID card faces will be smaller).
            img_h, img_w = image.shape[:2]
            relative_size = (w * h) / (img_w * img_h)

            # Heuristic confidence based on face size and position.
            # Passport photos are typically in the upper portion of a page.
            confidence = min(0.95, relative_size * 50)  # Scale to 0–0.95 range

            results.append(
                DetectionResult(
                    bbox=(int(x), int(y), int(w), int(h)),
                    confidence=confidence,
                    page_index=page_index,
                    detection_type=DetectionType.PHOTO,
                    strategy_name=self.name,
                    metadata={
                        "relative_size": round(relative_size, 4),
                        "detection_index": i,
                    },
                )
            )

        # Sort by confidence (largest face first).
        results.sort(key=lambda r: r.confidence, reverse=True)
        logger.info(
            "Haar: Found %d face(s) on page %d (best confidence: %.2f)",
            len(results),
            page_index,
            results[0].confidence if results else 0,
        )
        return results

    def is_available(self) -> bool:
        """Check if the Haar Cascade file is loadable."""
        self._load_cascade()
        return self._loaded

    @property
    def name(self) -> str:
        return "haar_cascade"
