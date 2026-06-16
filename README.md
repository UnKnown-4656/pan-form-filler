# PDF Auto-Completion Backend

Automatically extracts passport photos and handwritten signatures from scanned identity documents (Aadhaar, PAN, SSLC, etc.) and inserts them into application form PDFs.

Built for **CSC/PAN service center** workflows. Runs on **CPU-only** hardware with minimal dependencies.

---

## Features

- **Passport Photo Extraction** — Dual Haar Cascade + DNN face detection
- **Signature Extraction** — Contour analysis with heuristic scoring
- **Form Auto-Filling** — JSON-based template system for multiple form types
- **REST API** — FastAPI with auto-generated Swagger docs
- **Production-Ready** — Logging, error handling, file cleanup, configurable

## System Requirements

| Requirement | Minimum | Recommended |
|:---|:---|:---|
| Python | 3.12+ | 3.12+ |
| OS | Windows 10 | Windows 10/11 |
| CPU | Intel i5 (any gen) | Intel i5 6th gen+ |
| RAM | 4 GB | 8 GB |
| Disk | 500 MB free | 2 GB free |
| GPU | **Not required** | — |

---

## Quick Start

### 1. Clone and Setup

```bash
cd d:\Pan automation\pdf_autofill

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Download CV Models

```bash
python setup_models.py
```

This downloads the DNN face detection model (~10.7MB) and copies the Haar Cascade locally. The server works without DNN models (Haar-only mode), but accuracy will be lower.

### 3. Configure (Optional)

```bash
copy .env.example .env
# Edit .env to customize settings
```

### 4. Start the Server

```bash
python main.py
```

The server starts at `http://localhost:8000`.

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

---

## API Usage

### Extract Photo & Signature

```bash
curl -X POST http://localhost:8000/extract \
  -F "source_pdf=@scanned_documents.pdf"
```

**Response:**
```json
{
  "request_id": "a1b2c3d4-...",
  "photo": {
    "found": true,
    "confidence": 0.92,
    "page": 2,
    "bbox": [120, 80, 240, 320],
    "path": "extracted/a1b2c3d4.../photo.png",
    "strategy": "haar_cascade"
  },
  "signature": {
    "found": true,
    "confidence": 0.65,
    "page": 4,
    "bbox": [300, 900, 550, 970],
    "path": "extracted/a1b2c3d4.../signature.png",
    "strategy": "contour_analysis"
  },
  "processing_time_ms": 847.3
}
```

### Generate Completed Form

```bash
curl -X POST http://localhost:8000/process \
  -F "source_pdf=@scanned_documents.pdf" \
  -F "template_name=PAN_FORM_V1" \
  -F "form_pdf=@blank_pan_form.pdf" \
  -o completed_form.pdf
```

### List Templates

```bash
curl http://localhost:8000/templates
```

### Health Check

```bash
curl http://localhost:8000/health
```

---

## Project Structure

```
pdf_autofill/
├── app/
│   ├── api/
│   │   ├── router.py            # FastAPI endpoints
│   │   └── dependencies.py      # Request validation
│   ├── models/
│   │   ├── template.py          # Template schema (Pydantic)
│   │   ├── requests.py          # API request models
│   │   └── responses.py         # API response models
│   ├── services/
│   │   ├── processing.py        # Main orchestrator
│   │   ├── photo_detector.py    # Photo detection service
│   │   ├── signature_detector.py # Signature detection service
│   │   └── template_engine.py   # PDF form filling
│   ├── strategies/
│   │   ├── base.py              # Strategy interfaces
│   │   ├── haar_strategy.py     # Haar Cascade
│   │   ├── dnn_strategy.py      # OpenCV DNN
│   │   └── contour_strategy.py  # Signature contours
│   ├── utils/
│   │   ├── pdf_converter.py     # PDF → images
│   │   ├── image_processing.py  # CV utilities
│   │   └── file_manager.py      # File I/O, cleanup
│   ├── templates/
│   │   └── form_templates.json  # Template definitions
│   └── config.py                # Configuration
├── models/                       # CV model files
├── extracted/                    # Extracted images (per-request)
├── output/                       # Generated PDFs
├── tests/                        # Test suite
├── main.py                       # App entry point
├── setup_models.py               # Model downloader
├── requirements.txt
└── .env.example
```

## Adding Custom Form Templates

Edit `app/templates/form_templates.json`:

```json
{
  "MY_CUSTOM_FORM": {
    "description": "My Custom Application Form",
    "page_size": "A4",
    "fields": {
      "photo": {
        "page": 0,
        "x": 400,
        "y": 100,
        "width": 130,
        "height": 160,
        "required": true
      },
      "signature": {
        "page": 0,
        "x": 350,
        "y": 700,
        "width": 180,
        "height": 60,
        "required": true
      }
    }
  }
}
```

Coordinates are in **PDF points** (1 point = 1/72 inch). Origin is top-left corner.

**Tip:** Open your blank form PDF in a viewer that shows coordinates (e.g., Adobe Acrobat) to determine exact placement positions.

---

## Configuration

All settings can be overridden via environment variables (prefix: `PDFFILL_`) or a `.env` file.

| Variable | Default | Description |
|:---|:---|:---|
| `PDFFILL_PORT` | 8000 | Server port |
| `PDFFILL_MAX_WORKERS` | 1 | Concurrent processing limit |
| `PDFFILL_PHOTO_DETECTION_STRATEGY` | auto | `haar`, `dnn`, or `auto` |
| `PDFFILL_PDF_ZOOM_FACTOR` | 2.0 | PDF rendering quality |
| `PDFFILL_MAX_UPLOAD_SIZE_MB` | 50 | Max upload size |
| `PDFFILL_CLEANUP_TTL_HOURS` | 24 | Auto-delete extracted files after N hours |

See `.env.example` for the complete list.

---

## Production Deployment (Windows)

### Option 1: Direct (Simplest)

```bash
# Activate venv
venv\Scripts\activate

# Run with uvicorn
python main.py
```

### Option 2: Windows Service (via NSSM)

```bash
# Install NSSM (Non-Sucking Service Manager)
nssm install PDFAutoFill "d:\Pan automation\pdf_autofill\venv\Scripts\python.exe" "d:\Pan automation\pdf_autofill\main.py"
nssm set PDFAutoFill AppDirectory "d:\Pan automation\pdf_autofill"
nssm start PDFAutoFill
```

### Option 3: Task Scheduler

Create a Windows Task Scheduler entry to run `main.py` on system startup.

---

## Architecture

```
 ┌─────────────┐     ┌──────────────┐     ┌────────────────┐
 │  FastAPI     │────►│  Processing  │────►│  PDF Converter │
 │  Router      │     │  Service     │     │  (PyMuPDF)     │
 └─────────────┘     └──────┬───────┘     └────────────────┘
                            │
                    ┌───────┴───────┐
                    ▼               ▼
             ┌──────────┐   ┌──────────────┐
             │  Photo   │   │  Signature   │
             │ Detector │   │  Detector    │
             └────┬─────┘   └──────┬───────┘
                  │                │
           ┌──────┴──────┐        ▼
           ▼             ▼   ┌────────────┐
     ┌──────────┐  ┌────────┐│  Contour   │
     │  Haar    │  │  DNN   ││  Strategy  │
     │ Strategy │  │Strategy│└────────────┘
     └──────────┘  └────────┘
```

---

## Roadmap

| Version | Features |
|:---|:---|
| **V1 (current)** | Haar + DNN photo detection, contour signature detection, template engine |
| **V2** | YOLO photo detection, YOLO signature detection |
| **V3** | OCR integration, auto form detection, batch processing |
| **V4** | Web dashboard with operator verification UI |

---

## License

Internal use — CSC/PAN Service Center.
