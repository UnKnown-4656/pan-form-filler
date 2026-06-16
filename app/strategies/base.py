"""
Abstract base classes and protocols for detection strategies.

Defines the contracts that all detection strategies must implement.
This enables the Strategy pattern: swapping Haar → DNN → YOLO
without modifying the caller (PhotoDetector / SignatureDetector).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import numpy as np


class DetectionType(str, Enum):
    """Types of detectable elements."""
    PHOTO = "photo"
    SIGNATURE = "signature"


@dataclass
class DetectionResult:
    """
    Represents a single detection (face, signature, etc.).

    Attributes:
        bbox: Bounding box as (x, y, width, height) in pixel coordinates.
        confidence: Detection confidence score (0.0 to 1.0).
        page_index: Which PDF page this detection was found on.
        detection_type: Whether this is a photo or signature detection.
        strategy_name: Which strategy produced this detection (for logging).
        metadata: Optional extra data (e.g., face landmarks, contour stats).
    """
    bbox: tuple[int, int, int, int]
    confidence: float
    page_index: int
    detection_type: DetectionType
    strategy_name: str
    metadata: dict = field(default_factory=dict)

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    @property
    def area(self) -> int:
        return self.width * self.height


class PhotoDetectionStrategy(ABC):
    """
    Abstract strategy for detecting passport photos in page images.

    Implementations:
    - HaarStrategy: Fast Haar Cascade face detection
    - DNNStrategy: Accurate DNN-based face detection
    - (Future) YOLOStrategy: YOLO-based detection
    """

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect faces/photos in a single page image.

        Args:
            image: BGR page image as numpy array.
            page_index: Zero-based index of the PDF page.

        Returns:
            List of DetectionResult objects, sorted by confidence (descending).
            Empty list if no detections found.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this strategy's model/cascade files are available."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name for logging."""
        ...


class SignatureDetectionStrategy(ABC):
    """
    Abstract strategy for detecting handwritten signatures.

    Implementations:
    - ContourStrategy: Heuristic contour analysis
    - (Future) YOLOSignatureStrategy: YOLO-based detection
    """

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        page_index: int,
    ) -> List[DetectionResult]:
        """
        Detect signatures in a single page image.

        Args:
            image: BGR page image as numpy array.
            page_index: Zero-based index of the PDF page.

        Returns:
            List of DetectionResult objects, sorted by score (descending).
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this strategy is ready to use."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name for logging."""
        ...
