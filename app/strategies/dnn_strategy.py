"""
OpenCV DNN face detection strategy.

Uses the pre-trained SSD-ResNet10 model (Caffe) for robust face detection.
Significantly more accurate than Haar Cascade, especially for:
- Tilted/rotated faces
- Poor lighting
- Partially occluded faces

Model files required (~10.7MB total):
- deploy.prototxt (~28KB)
- res10_300x300_ssd_iter_140000.caffemodel (~10.7MB)

Performance: ~150–300ms per page on old i5 (CPU only).
Accuracy: ~95%.
"""

import logging
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from app.config import settings
from app.strategies.base import DetectionResult, DetectionType, PhotoDetectionStrategy
from app.utils.image_processing import enhance_contrast

logger = logging.getLogger(__name__)

# Expected model filenames.
_PROTOTXT_NAME = "deploy.prototxt"
_MODEL_NAME = "res10_300x300_ssd_iter_140000.caffemodel"


class DNNStrategy(PhotoDetectionStrategy):
    """
    DNN-based face detection using OpenCV's DNN module.

    Uses the SSD (Single Shot Detector) architecture with a ResNet-10
    backbone, trained on face data. The model runs entirely on CPU
    via OpenCV's optimized DNN inference engine.

    Pros:
    - Very high accuracy (~95%)
    - Handles rotation, occlusion, varied lighting
    - Single forward pass — consistent performance

    Cons:
    - ~10× slower than Haar on CPU
    - Requires two model files (~10.7MB)
    - Fixed input size (300×300) limits very small face detection
    """

    def __init__(self, models_dir: Optional[Path] = None) -> None:
        self._models_dir = models_dir or settings.MODELS_DIR
        self._net: Optional[cv2.dnn.Net] = None
        self._loaded = False

    def _load_model(self) -> None:
        """Lazy-load the DNN model. Only called once."""
        if self._loaded:
            return

        prototxt_path = self._models_dir / _PROTOTXT_NAME
        model_path = self._models_dir / _MODEL_NAME

        if not prototxt_path.exists():
            logger.warning("DNN prototxt not found: %s", prototxt_path)
            return

        if not model_path.exists():
            logger.warning("DNN model not found: %s", model_path)
            return

        try:
            self._net = cv2.dnn.readNetFromCaffe(
                str(prototxt_path), str(model_path)
            )
            # Force CPU backend (no GPU).
            self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

            self._loaded = True
            logger.info("DNN face detector loaded successfully")

        except cv2.error as e:
            logger.error("Failed to load DNN model: %s", e)
            self._loaded = False

    def detect(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect faces using the DNN model.

        The model processes a 300×300 blob and outputs face detections
        with confidence scores and bounding box coordinates.
        """
        self._load_model()

        if not self._loaded or self._net is None:
            logger.warning("DNN model not available, returning empty results")
            return []

        # Enhance contrast for scanned documents.
        enhanced = enhance_contrast(image)

        img_h, img_w = enhanced.shape[:2]
        input_size = settings.DNN_INPUT_SIZE

        # Create a normalized blob for the DNN.
        # Mean subtraction values are specific to the training data.
        blob = cv2.dnn.blobFromImage(
            enhanced,
            scalefactor=1.0,
            size=(input_size, input_size),
            mean=(104.0, 177.0, 123.0),  # ImageNet-style mean subtraction
            swapRB=False,  # Image is already BGR
            crop=False,
        )

        # Forward pass.
        self._net.setInput(blob)
        detections = self._net.forward()

        results: List[DetectionResult] = []
        threshold = settings.DNN_CONFIDENCE_THRESHOLD

        # detections shape: (1, 1, N, 7)
        # Each detection: [batch_id, class_id, confidence, x1, y1, x2, y2]
        # Coordinates are normalized to [0, 1].
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])

            if confidence < threshold:
                continue

            # Scale bounding box back to image coordinates.
            x1 = int(detections[0, 0, i, 3] * img_w)
            y1 = int(detections[0, 0, i, 4] * img_h)
            x2 = int(detections[0, 0, i, 5] * img_w)
            y2 = int(detections[0, 0, i, 6] * img_h)

            # Clamp to image boundaries.
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img_w, x2)
            y2 = min(img_h, y2)

            w = x2 - x1
            h = y2 - y1

            # Skip degenerate detections.
            if w <= 0 or h <= 0:
                continue

            results.append(
                DetectionResult(
                    bbox=(x1, y1, w, h),
                    confidence=confidence,
                    page_index=page_index,
                    detection_type=DetectionType.PHOTO,
                    strategy_name=self.name,
                    metadata={
                        "raw_coords": [
                            float(detections[0, 0, i, 3]),
                            float(detections[0, 0, i, 4]),
                            float(detections[0, 0, i, 5]),
                            float(detections[0, 0, i, 6]),
                        ],
                    },
                )
            )

        # Sort by confidence (highest first).
        results.sort(key=lambda r: r.confidence, reverse=True)

        logger.info(
            "DNN: Found %d face(s) on page %d (best confidence: %.2f)",
            len(results),
            page_index,
            results[0].confidence if results else 0,
        )
        return results

    def is_available(self) -> bool:
        """Check if both model files exist."""
        prototxt_path = self._models_dir / _PROTOTXT_NAME
        model_path = self._models_dir / _MODEL_NAME
        return prototxt_path.exists() and model_path.exists()

    @property
    def name(self) -> str:
        return "dnn_ssd_resnet10"
