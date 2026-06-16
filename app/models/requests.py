"""
Pydantic models for API request validation.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    """
    Request model for the /extract endpoint.

    The actual PDF file is received via multipart form upload,
    not via this model. This handles any additional form fields.
    """
    pass  # PDF comes via UploadFile parameter


class ProcessRequest(BaseModel):
    """
    Request model for the /process endpoint (form fields only).

    The PDF files are received via multipart form upload parameters.
    This model captures the non-file form fields.
    """
    template_name: str = Field(
        ...,
        description="Name of the form template to use (e.g., 'PAN_FORM_V1').",
        min_length=1,
        max_length=100,
    )
