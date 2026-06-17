"""
FastAPI router — all HTTP endpoints for the PDF auto-completion API.

Endpoints:
- POST /extract    — Extract photo and signature from a scanned PDF
- POST /process    — Full pipeline: extract → fill form → return completed PDF
- GET  /templates  — List available form templates
- POST /templates/{name} — Save or update a template
- DELETE /templates/{name} — Delete a template
- POST /pdf/render-page — Render a PDF page as PNG
- GET  /health     — Health check with system status
"""

import asyncio
import io
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

import pymupdf

from app.api.dependencies import validate_pdf_upload
from app.models.responses import (
    DetectionInfo,
    ErrorResponse,
    ExtractResponse,
    HealthResponse,
    TemplateInfo,
    TemplatesResponse,
)
from app.models.template import FormTemplate, FieldPlacement
from app.services.processing import ProcessingService

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level service instance — initialized by the app lifespan.
# This avoids re-creating the service (and re-loading models) per request.
_service: Optional[ProcessingService] = None
_start_time: float = time.time()


def get_service() -> ProcessingService:
    """Get the initialized processing service."""
    global _service
    if _service is None:
        _service = ProcessingService()
    return _service


def init_service() -> None:
    """Initialize the service at app startup."""
    global _service, _start_time
    _service = ProcessingService()
    _start_time = time.time()
    logger.info("Processing service initialized at startup")


# ── POST /extract ────────────────────────────────────────────────────────────


@router.post(
    "/extract",
    response_model=ExtractResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Extract photo and signature from a scanned PDF",
    description=(
        "Upload a scanned PDF containing identity documents. "
        "The system will detect and extract the passport photo "
        "and handwritten signature, saving them as separate PNG images."
    ),
)
async def extract(
    source_pdf: UploadFile = File(
        ..., description="Scanned PDF containing identity documents"
    ),
) -> ExtractResponse:
    """Extract photo and signature from a scanned PDF."""
    # Validate and read the PDF.
    pdf_bytes = await validate_pdf_upload(source_pdf, "source_pdf")

    service = get_service()

    try:
        # Run CPU-bound processing in a thread pool to avoid blocking
        # the async event loop.
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, service.extract, pdf_bytes
        )

        return ExtractResponse(
            request_id=result["request_id"],
            photo=DetectionInfo(**result["photo"]),
            signature=DetectionInfo(**result["signature"]),
            processing_time_ms=result["processing_time_ms"],
        )

    except RuntimeError as e:
        logger.error("Extraction failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Unexpected error during extraction: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )


# ── POST /process ────────────────────────────────────────────────────────────


@router.post(
    "/process",
    responses={
        200: {"content": {"application/pdf": {}}},
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Extract and fill a form PDF",
    description=(
        "Upload a scanned PDF with identity documents and a blank form PDF. "
        "The system extracts the photo and signature, inserts them into "
        "the form at template-defined positions, and returns the completed PDF."
    ),
)
async def process(
    source_pdf: UploadFile = File(
        ..., description="Scanned PDF containing identity documents"
    ),
    template_name: str = Form(
        ..., description="Form template name (e.g., 'PAN_FORM_V1')"
    ),
    form_pdf: Optional[UploadFile] = File(
        default=None,
        description="Optional blank form PDF. If not provided, uses pre-stored form.",
    ),
    custom_coords: Optional[str] = Form(
        default=None,
        description="Optional JSON string with custom field coordinates to override template",
    ),
) -> FileResponse:
    """Extract photo/signature and generate a completed form PDF."""
    # Validate source PDF.
    source_bytes = await validate_pdf_upload(source_pdf, "source_pdf")

    # Validate form PDF if provided.
    form_bytes: Optional[bytes] = None
    if form_pdf is not None:
        form_bytes = await validate_pdf_upload(form_pdf, "form_pdf")

    service = get_service()

    # Validate template exists.
    template = service.template_engine.get_template(template_name)
    if template is None:
        available = service.template_engine.list_templates()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Template '{template_name}' not found. "
                f"Available templates: {', '.join(available) or '(none)'}"
            ),
        )

    # Parse custom_coords
    parsed_custom_coords = None
    if custom_coords:
        try:
            parsed_custom_coords = json.loads(custom_coords)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in custom_coords",
            )

    try:
        loop = asyncio.get_event_loop()

        if form_bytes:
            output_path, _ = await loop.run_in_executor(
                None,
                service.process,
                source_bytes,
                template_name,
                form_bytes,
                None,  # form_pdf_path
                None,  # request_id
                parsed_custom_coords,
            )
        else:
            # For now, require a form PDF upload.
            # Future: look up pre-stored form by template name.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No form PDF provided. Please upload a blank form PDF "
                    "via the 'form_pdf' field."
                ),
            )

        if not output_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Output PDF was not generated.",
            )

        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=f"completed_{template_name}.pdf",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Processing failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )


# ── GET /templates ────────────────────────────────────────────────────────────


@router.get(
    "/templates",
    response_model=TemplatesResponse,
    summary="List available form templates",
)
async def list_templates() -> TemplatesResponse:
    """Return all available form template definitions."""
    service = get_service()
    template_names = service.template_engine.list_templates()

    templates = []
    for name in template_names:
        tmpl = service.template_engine.get_template(name)
        if tmpl:
            templates.append(
                TemplateInfo(
                    name=name,
                    description=tmpl.description,
                    fields=list(tmpl.fields.keys()),
                )
            )

    return TemplatesResponse(templates=templates)


# ── GET /templates/{template_name} ────────────────────────────────────────────


@router.get(
    "/templates/{template_name}",
    summary="Get a form template by name",
    responses={
        200: {"content": {"application/json": {}}},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_template(template_name: str) -> JSONResponse:
    """Get a form template by name."""
    try:
        service = get_service()
        template = service.template_engine.get_template(template_name)
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found",
            )
        # Convert to dict for response
        template_dict = template.model_dump()
        return JSONResponse(content={"status": "success", "template": template_dict})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get template: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template: {str(e)}",
        )


# ── POST /templates/{template_name} ───────────────────────────────────────────


@router.post(
    "/templates/{template_name}",
    summary="Save or update a form template",
    responses={
        200: {"content": {"application/json": {}}},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def save_template(
    template_name: str,
    template_data: Dict[str, Any]
) -> JSONResponse:
    """Save or update a form template."""
    try:
        # Get template data from JSON body
        description = template_data.get("description", "")
        page_size = template_data.get("page_size", "A4")
        fields_dict = template_data.get("fields", {})

        # Parse fields into FieldPlacement objects
        parsed_fields: Dict[str, FieldPlacement] = {}
        for field_name, field_data in fields_dict.items():
            parsed_fields[field_name] = FieldPlacement(**field_data)

        # Create FormTemplate
        template = FormTemplate(
            description=description,
            page_size=page_size,
            fields=parsed_fields,
        )

        service = get_service()
        service.template_engine.save_template(template_name, template)
        # Reload templates to ensure cache is updated
        service.template_engine.load_templates()

        return JSONResponse(
            content={"status": "success", "template": template_name}
        )

    except Exception as e:
        logger.error("Failed to save template: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save template: {str(e)}",
        )


# ── DELETE /templates/{template_name} ─────────────────────────────────────────


@router.delete(
    "/templates/{template_name}",
    summary="Delete a form template",
    responses={
        200: {"content": {"application/json": {}}},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def delete_template(template_name: str) -> JSONResponse:
    """Delete a form template."""
    try:
        service = get_service()
        deleted = service.template_engine.delete_template(template_name)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found",
            )

        return JSONResponse(
            content={"status": "success", "template": template_name}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete template: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete template: {str(e)}",
        )


# ── POST /pdf/render-page ─────────────────────────────────────────────────────


@router.post(
    "/pdf/render-page",
    summary="Render a PDF page as a PNG image",
    responses={
        200: {"content": {"image/png": {}}},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def render_pdf_page(
    pdf: UploadFile = File(...),
    page: int = Form(0, description="Zero-based page index to render"),
) -> StreamingResponse:
    """Render a specific page of a PDF as a PNG image."""
    pdf_bytes = await validate_pdf_upload(pdf, "pdf")

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        if page < 0 or page >= len(doc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Page index {page} out of range. PDF has {len(doc)} pages.",
            )

        page_obj = doc[page]
        page_rect = page_obj.rect
        pix = page_obj.get_pixmap()

        # Prepare response with page dimensions in headers
        img_data = io.BytesIO(pix.tobytes("png"))
        
        response = StreamingResponse(img_data, media_type="image/png")
        response.headers["X-Page-Width-Points"] = str(page_rect.width)
        response.headers["X-Page-Height-Points"] = str(page_rect.height)
        response.headers["X-Page-Count"] = str(len(doc))
        
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to render PDF page: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render PDF page: {str(e)}",
        )


# ── GET /health ───────────────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check() -> HealthResponse:
    """Return system health status and loaded models."""
    import cv2

    from app import __version__

    service = get_service()
    strategies = service.get_available_strategies()

    return HealthResponse(
        status="healthy",
        version=__version__,
        models_loaded={
            "haar_cascade": "haar_cascade" in strategies.get("photo", []),
            "dnn_resnet10": "dnn_ssd_resnet10" in strategies.get("photo", []),
            "contour_analysis": "contour_analysis" in strategies.get("signature", []),
        },
        available_strategies=(
            strategies.get("photo", []) + strategies.get("signature", [])
        ),
        uptime_seconds=round(time.time() - _start_time, 1),
        templates_count=len(service.template_engine.list_templates()),
    )


# ── POST /cleanup ─────────────────────────────────────────────────────────────


@router.post(
    "/cleanup",
    summary="Run cleanup of old extracted files",
    include_in_schema=False,  # Internal/admin endpoint
)
async def cleanup() -> JSONResponse:
    """Remove extracted files older than the configured TTL."""
    service = get_service()
    removed = service.cleanup_old_files()
    return JSONResponse(
        content={"removed_directories": removed},
    )
