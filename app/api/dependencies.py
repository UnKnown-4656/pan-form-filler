"""
FastAPI dependencies — shared validation and injection.

Provides reusable dependencies for file validation, size limits,
and content type checking.
"""

import logging
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.config import settings

logger = logging.getLogger(__name__)

# Allowed MIME types for PDF uploads.
_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",  # Some clients send this for PDFs
}


async def validate_pdf_upload(
    file: UploadFile,
    field_name: str = "file",
) -> bytes:
    """
    Validate an uploaded PDF file and return its content as bytes.

    Checks:
    - Content type is PDF (or octet-stream)
    - File is not empty
    - File does not exceed size limit
    - File starts with PDF magic bytes (%PDF)

    Args:
        file: The uploaded file from FastAPI.
        field_name: Name of the form field (for error messages).

    Returns:
        Raw PDF bytes.

    Raises:
        HTTPException: If validation fails.
    """
    # Check content type.
    content_type = file.content_type or ""
    if content_type not in _PDF_CONTENT_TYPES:
        # Also accept files with .pdf extension regardless of MIME type.
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"Field '{field_name}': Expected a PDF file, "
                    f"got '{content_type}'. "
                    f"Accepted types: application/pdf"
                ),
            )

    # Read file content.
    content = await file.read()

    # Check not empty.
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field '{field_name}': Uploaded file is empty.",
        )

    # Check size limit.
    max_bytes = settings.max_upload_bytes
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Field '{field_name}': File size ({len(content)} bytes) "
                f"exceeds maximum ({max_bytes} bytes / "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB)."
            ),
        )

    # Check PDF magic bytes.
    if not content[:5].startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Field '{field_name}': File does not appear to be a valid PDF "
                f"(missing PDF header)."
            ),
        )

    logger.debug(
        "Validated PDF upload: %s (%d bytes)",
        file.filename,
        len(content),
    )
    return content
