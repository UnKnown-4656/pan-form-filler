"""
PDF-to-image conversion using PyMuPDF.

Encapsulates all PyMuPDF (pymupdf) interactions for converting PDF pages
to numpy arrays suitable for OpenCV processing. Handles:
- Page-by-page rendering at configurable zoom/DPI
- Memory-efficient iteration (one page at a time)
- Direct conversion to numpy arrays (no temp files)
"""

import logging
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import numpy as np
import pymupdf  # PyMuPDF — modern import name

from app.config import settings

logger = logging.getLogger(__name__)


# Type alias for a page image with its page index.
PageImage = Tuple[int, np.ndarray]


class PDFConverter:
    """
    Converts PDF pages to images for computer vision processing.

    Uses PyMuPDF's built-in renderer (MuPDF C engine) — extremely fast
    and doesn't require external dependencies like poppler.
    """

    def __init__(self, zoom_factor: Optional[float] = None) -> None:
        """
        Args:
            zoom_factor: Scaling factor for rendering. 2.0 = 144 DPI.
                         Higher values give better quality but use more RAM.
        """
        self.zoom_factor = zoom_factor or settings.PDF_ZOOM_FACTOR
        self._matrix = pymupdf.Matrix(self.zoom_factor, self.zoom_factor)

    def pdf_to_images(self, pdf_path: Path) -> List[PageImage]:
        """
        Convert all pages of a PDF to numpy arrays.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of (page_index, image_array) tuples. Images are in BGR
            format (OpenCV convention).

        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            RuntimeError: If the PDF cannot be opened or rendered.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        images: List[PageImage] = []

        try:
            doc = pymupdf.open(str(pdf_path))
            page_count = len(doc)
            logger.info(
                "Opened PDF: %s (%d pages, zoom=%.1f)",
                pdf_path.name,
                page_count,
                self.zoom_factor,
            )

            for page_idx in range(page_count):
                image = self._render_page(doc, page_idx)
                images.append((page_idx, image))

            doc.close()
            logger.info("Converted %d pages to images", len(images))

        except pymupdf.FileDataError as e:
            raise RuntimeError(f"Cannot open PDF (corrupted or encrypted): {e}") from e
        except Exception as e:
            raise RuntimeError(f"PDF conversion failed: {e}") from e

        return images

    def pdf_to_images_generator(
        self, pdf_path: Path
    ) -> Generator[PageImage, None, None]:
        """
        Memory-efficient generator that yields one page image at a time.

        Use this for large PDFs to avoid loading all page images into RAM
        simultaneously.

        Args:
            pdf_path: Path to the PDF file.

        Yields:
            (page_index, image_array) tuples.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            doc = pymupdf.open(str(pdf_path))
            page_count = len(doc)
            logger.info(
                "Streaming PDF: %s (%d pages, zoom=%.1f)",
                pdf_path.name,
                page_count,
                self.zoom_factor,
            )

            for page_idx in range(page_count):
                yield (page_idx, self._render_page(doc, page_idx))

            doc.close()

        except pymupdf.FileDataError as e:
            raise RuntimeError(f"Cannot open PDF (corrupted or encrypted): {e}") from e

    def pdf_to_images_from_bytes(self, pdf_bytes: bytes) -> List[PageImage]:
        """
        Convert PDF from raw bytes (useful for uploaded files without saving to disk).

        Args:
            pdf_bytes: Raw PDF content.

        Returns:
            List of (page_index, image_array) tuples in BGR format.
        """
        images: List[PageImage] = []

        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            logger.info("Opened PDF from bytes (%d pages)", page_count)

            for page_idx in range(page_count):
                image = self._render_page(doc, page_idx)
                images.append((page_idx, image))

            doc.close()

        except Exception as e:
            raise RuntimeError(f"PDF conversion from bytes failed: {e}") from e

        return images

    def get_page_count(self, pdf_path: Path) -> int:
        """Return the number of pages in a PDF without rendering."""
        doc = pymupdf.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count

    def _render_page(self, doc: pymupdf.Document, page_idx: int) -> np.ndarray:
        """
        Render a single page to a BGR numpy array.

        Args:
            doc: Open PyMuPDF document.
            page_idx: Zero-based page index.

        Returns:
            numpy array of shape (H, W, 3) in BGR color order.
        """
        page = doc.load_page(page_idx)
        pixmap = page.get_pixmap(matrix=self._matrix, alpha=False)

        # Convert pixmap to numpy array.
        # PyMuPDF pixmaps are in RGB order; OpenCV expects BGR.
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, 3
        )
        # RGB → BGR for OpenCV compatibility.
        image = image[:, :, ::-1].copy()

        logger.debug(
            "Rendered page %d: %dx%d px",
            page_idx,
            pixmap.width,
            pixmap.height,
        )

        return image
