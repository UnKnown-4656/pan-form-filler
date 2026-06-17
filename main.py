"""
FastAPI application entry point.

Configures:
- Application metadata (title, description, version)
- Lifespan events (startup model loading, shutdown cleanup)
- CORS middleware
- Logging
- Router mounting

Run with:
    python main.py
    # or
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import init_service, router
from app.config import settings


def _configure_logging() -> None:
    """Set up structured logging for the application."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
    - Configure logging
    - Initialize processing service (loads CV models, templates)
    - Validate critical resources

    Shutdown:
    - Run final cleanup
    """
    # ── Startup ──
    _configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("PDF Auto-Completion Backend v%s", __version__)
    logger.info("=" * 60)
    logger.info("Configuration:")
    logger.info("  Host: %s:%d", settings.HOST, settings.PORT)
    logger.info("  Max workers: %d", settings.MAX_WORKERS)
    logger.info("  Max upload: %d MB", settings.MAX_UPLOAD_SIZE_MB)
    logger.info("  Photo strategy: %s", settings.PHOTO_DETECTION_STRATEGY)
    logger.info("  PDF zoom: %.1f", settings.PDF_ZOOM_FACTOR)
    logger.info("  Extracted dir: %s", settings.EXTRACTED_DIR)
    logger.info("  Output dir: %s", settings.OUTPUT_DIR)
    logger.info("  Models dir: %s", settings.MODELS_DIR)

    # Initialize the processing service (loads models + templates).
    init_service()

    logger.info("=" * 60)
    logger.info("Server ready — accepting requests")
    logger.info("=" * 60)

    yield

    # ── Shutdown ──
    logger.info("Shutting down — running final cleanup...")
    from app.api.router import get_service
    try:
        service = get_service()
        removed = service.cleanup_old_files()
        logger.info("Cleanup complete: removed %d old directories", removed)
    except Exception as e:
        logger.warning("Cleanup on shutdown failed: %s", e)

    logger.info("Goodbye.")


# Create the FastAPI application.
app = FastAPI(
    title="PDF Auto-Completion API",
    description=(
        "Automatically extracts passport photos and handwritten signatures "
        "from scanned identity documents (Aadhaar, PAN, etc.) and inserts "
        "them into application form PDFs.\n\n"
        "Built for CSC/PAN service center workflows. "
        "Runs on CPU-only hardware with minimal dependencies."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware — allow local development frontends.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the API router.
app.include_router(router, prefix="/api/v1", tags=["PDF Processing"])

# Also mount at root for backward compatibility.
app.include_router(router, tags=["PDF Processing (root)"])

# Ensure required folders exist before mounting static files to avoid Starlette errors
from pathlib import Path
Path("static").mkdir(parents=True, exist_ok=True)
settings.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount extracted files folder to serve the cropped image previews
app.mount("/extracted", StaticFiles(directory=str(settings.EXTRACTED_DIR)), name="extracted")

# Mount output files folder to serve filled form PDFs
app.mount("/output", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="output")

# Serve index.html on root path
@app.get("/", include_in_schema=False)
async def read_index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.MAX_WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False,  # Disable reload in production
    )
