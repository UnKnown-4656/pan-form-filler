"""
Shared image processing utilities for detection pipelines.

Contains common CV operations used by both photo and signature detectors:
- Grayscale conversion
- Adaptive thresholding
- Morphological operations
- Contour analysis helpers
- Image cropping and saving
- CLAHE enhancement for shadow normalization
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# Type alias for a bounding box: (x, y, width, height)
BBox = Tuple[int, int, int, int]


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a BGR image to grayscale. No-op if already grayscale."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def adaptive_threshold(
    gray: np.ndarray,
    block_size: int = 15,
    c_value: int = 10,
) -> np.ndarray:
    """
    Apply adaptive Gaussian thresholding.

    Handles uneven lighting from scanners better than global thresholding.

    Args:
        gray: Grayscale image.
        block_size: Size of the pixel neighborhood (must be odd).
        c_value: Constant subtracted from the mean.

    Returns:
        Binary image (foreground=255, background=0).
    """
    # Ensure block_size is odd.
    if block_size % 2 == 0:
        block_size += 1

    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        c_value,
    )


def morphological_close(
    binary: np.ndarray,
    kernel_size: int = 5,
) -> np.ndarray:
    """
    Apply morphological closing to connect broken strokes.

    Closing = dilation followed by erosion. Fills small gaps in signature
    strokes without significantly expanding the overall shape.

    Args:
        binary: Binary image.
        kernel_size: Size of the structuring element.

    Returns:
        Processed binary image.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (kernel_size, kernel_size)
    )
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


def morphological_dilate(
    binary: np.ndarray,
    kernel_size: int = 3,
    iterations: int = 1,
) -> np.ndarray:
    """
    Dilate foreground regions to merge nearby components.

    Args:
        binary: Binary image.
        kernel_size: Size of the structuring element.
        iterations: Number of dilation passes.

    Returns:
        Dilated binary image.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (kernel_size, kernel_size)
    )
    return cv2.dilate(binary, kernel, iterations=iterations)


def find_contours(binary: np.ndarray) -> List[np.ndarray]:
    """
    Find external contours in a binary image.

    Uses RETR_EXTERNAL to get only the outermost contours
    (ignores nested contours inside shapes).

    Args:
        binary: Binary image.

    Returns:
        List of contour arrays.
    """
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    return list(contours)


def contour_solidity(contour: np.ndarray) -> float:
    """
    Compute contour solidity (area / convex hull area).

    Low solidity (~0.2–0.5) = irregular shape (like handwriting).
    High solidity (~0.8–1.0) = compact shape (like rectangles, QR codes).

    Args:
        contour: OpenCV contour.

    Returns:
        Solidity value between 0.0 and 1.0.
    """
    area = cv2.contourArea(contour)
    if area <= 0:
        return 0.0
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    if hull_area <= 0:
        return 0.0
    return area / hull_area


def stroke_density(binary_roi: np.ndarray) -> float:
    """
    Compute the ratio of foreground pixels to total pixels in a region.

    Low density (~0.05–0.25) = sparse strokes (like signatures).
    High density (~0.4+) = dense text blocks.

    Args:
        binary_roi: Binary image of the region of interest.

    Returns:
        Density value between 0.0 and 1.0.
    """
    total = binary_roi.size
    if total == 0:
        return 0.0
    foreground = np.count_nonzero(binary_roi)
    return foreground / total


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization).

    Normalizes shadows from pasted photos and uneven scanner lighting.

    Args:
        image: BGR or grayscale image.

    Returns:
        Contrast-enhanced image (same shape and type).
    """
    if len(image.shape) == 3:
        # Convert to LAB, apply CLAHE to L channel, convert back.
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(l_channel)
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    else:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)


def crop_region(image: np.ndarray, bbox: BBox) -> np.ndarray:
    """
    Crop a region from an image using a bounding box.

    Automatically clamps coordinates to image boundaries.

    Args:
        image: Source image (BGR or grayscale).
        bbox: (x, y, width, height) bounding box.

    Returns:
        Cropped image region.
    """
    x, y, w, h = bbox
    img_h, img_w = image.shape[:2]

    # Clamp to image boundaries.
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(img_w, x + w)
    y2 = min(img_h, y + h)

    return image[y1:y2, x1:x2].copy()


def expand_bbox(
    bbox: BBox,
    image_shape: Tuple[int, int],
    expand_top: float = 0.3,
    expand_bottom: float = 0.5,
    expand_sides: float = 0.4,
) -> BBox:
    """
    Expand a bounding box by specified ratios, clamped to image bounds.

    Used to expand a face bounding box to include the full passport
    photo area (hair, ears, neck, shoulders).

    Args:
        bbox: Original (x, y, w, h) bounding box.
        image_shape: (height, width) of the source image.
        expand_top: Ratio to expand upward.
        expand_bottom: Ratio to expand downward.
        expand_sides: Ratio to expand left and right.

    Returns:
        Expanded (x, y, w, h) bounding box.
    """
    x, y, w, h = bbox
    img_h, img_w = image_shape

    # Calculate expansion amounts.
    dx = int(w * expand_sides)
    dy_top = int(h * expand_top)
    dy_bottom = int(h * expand_bottom)

    # Expand and clamp.
    new_x = max(0, x - dx)
    new_y = max(0, y - dy_top)
    new_x2 = min(img_w, x + w + dx)
    new_y2 = min(img_h, y + h + dy_bottom)

    return (new_x, new_y, new_x2 - new_x, new_y2 - new_y)


def save_image(image: np.ndarray, path: Path) -> Path:
    """
    Save a numpy array as a PNG image.

    Uses Pillow for saving (better PNG compression than OpenCV).

    Args:
        image: BGR or grayscale numpy array.
        path: Output file path.

    Returns:
        The path the image was saved to.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if len(image.shape) == 3:
        # BGR → RGB for Pillow.
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)
    else:
        pil_image = Image.fromarray(image)

    pil_image.save(str(path), format="PNG", optimize=True)
    logger.info("Saved image: %s (%dx%d)", path, image.shape[1], image.shape[0])
    return path


def compute_image_hash(image: np.ndarray, hash_size: int = 8) -> str:
    """
    Compute a simple perceptual hash (average hash) of an image.

    Useful for deduplication when multiple pages contain the same photo.

    Args:
        image: Input image.
        hash_size: Hash grid size (8 = 64-bit hash).

    Returns:
        Hex string of the perceptual hash.
    """
    gray = to_grayscale(image)
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    mean_val = resized.mean()
    bits = (resized > mean_val).flatten()
    hash_value = 0
    for bit in bits:
        hash_value = (hash_value << 1) | int(bit)
    return format(hash_value, f"0{hash_size * hash_size // 4}x")
