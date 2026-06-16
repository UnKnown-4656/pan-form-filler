"""
Setup script — downloads and verifies required CV model files.

Downloads:
1. OpenCV DNN face detection model (SSD-ResNet10, Caffe format)
   - deploy.prototxt (~28KB)
   - res10_300x300_ssd_iter_140000.caffemodel (~10.7MB)

2. Haar Cascade XML (usually bundled with OpenCV, but we copy locally
   for deployment consistency)

Run once after installation:
    python setup_models.py
"""

import hashlib
import shutil
import sys
from pathlib import Path
from urllib.request import urlretrieve

# Model directory relative to this script.
MODELS_DIR = Path(__file__).parent / "models"

# DNN model download URLs (from OpenCV's GitHub).
DNN_FILES = {
    "deploy.prototxt": {
        "url": (
            "https://raw.githubusercontent.com/opencv/opencv/"
            "master/samples/dnn/face_detector/deploy.prototxt"
        ),
        "size_approx_kb": 28,
    },
    "res10_300x300_ssd_iter_140000.caffemodel": {
        "url": (
            "https://raw.githubusercontent.com/opencv/opencv_3rdparty/"
            "dnn_samples_face_detector_20170830/"
            "res10_300x300_ssd_iter_140000.caffemodel"
        ),
        "size_approx_kb": 10700,
    },
}


def download_file(url: str, dest: Path) -> bool:
    """Download a file from a URL to a local path."""
    print(f"  Downloading: {dest.name}")
    print(f"  From: {url}")
    try:
        urlretrieve(url, str(dest))
        size_kb = dest.stat().st_size / 1024
        print(f"  ✓ Downloaded ({size_kb:.0f} KB)")
        return True
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return False


def copy_haar_cascade(dest_dir: Path) -> bool:
    """Copy Haar Cascade from OpenCV's bundled data to our models dir."""
    try:
        import cv2
        src = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        if src.exists():
            dest = dest_dir / "haarcascade_frontalface_default.xml"
            shutil.copy2(str(src), str(dest))
            print(f"  ✓ Copied Haar Cascade from OpenCV data")
            return True
        else:
            print(f"  ✗ Haar Cascade not found at: {src}")
            return False
    except ImportError:
        print("  ✗ OpenCV not installed. Install with: pip install opencv-python-headless")
        return False


def verify_models(models_dir: Path) -> bool:
    """Verify all required model files exist and have reasonable sizes."""
    all_good = True

    for filename, info in DNN_FILES.items():
        path = models_dir / filename
        if not path.exists():
            print(f"  ✗ Missing: {filename}")
            all_good = False
        else:
            size_kb = path.stat().st_size / 1024
            expected_kb = info["size_approx_kb"]
            if size_kb < expected_kb * 0.5:
                print(
                    f"  ⚠ {filename}: suspiciously small "
                    f"({size_kb:.0f} KB, expected ~{expected_kb} KB)"
                )
                all_good = False
            else:
                print(f"  ✓ {filename} ({size_kb:.0f} KB)")

    haar_path = models_dir / "haarcascade_frontalface_default.xml"
    if haar_path.exists():
        print(f"  ✓ haarcascade_frontalface_default.xml")
    else:
        print(f"  ⚠ haarcascade_frontalface_default.xml not found (optional — OpenCV has bundled copy)")

    return all_good


def main() -> int:
    """Main setup routine."""
    print("=" * 60)
    print("PDF Auto-Completion Backend — Model Setup")
    print("=" * 60)

    # Create models directory.
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nModels directory: {MODELS_DIR}")

    # Step 1: Download DNN model files.
    print("\n── Step 1: DNN Face Detection Model ──")
    for filename, info in DNN_FILES.items():
        dest = MODELS_DIR / filename
        if dest.exists():
            size_kb = dest.stat().st_size / 1024
            print(f"  ✓ {filename} already exists ({size_kb:.0f} KB)")
        else:
            success = download_file(info["url"], dest)
            if not success:
                print(
                    f"\n  Manual download instructions:"
                    f"\n  1. Download from: {info['url']}"
                    f"\n  2. Save to: {dest}"
                )

    # Step 2: Copy Haar Cascade.
    print("\n── Step 2: Haar Cascade Classifier ──")
    haar_dest = MODELS_DIR / "haarcascade_frontalface_default.xml"
    if haar_dest.exists():
        print(f"  ✓ Already exists")
    else:
        copy_haar_cascade(MODELS_DIR)

    # Step 3: Verify.
    print("\n── Step 3: Verification ──")
    all_good = verify_models(MODELS_DIR)

    print("\n" + "=" * 60)
    if all_good:
        print("✓ All models ready!")
        print("\nTo start the server:")
        print("  python main.py")
        return 0
    else:
        print("⚠ Some models are missing or incomplete.")
        print("The server will still work with Haar Cascade (bundled with OpenCV).")
        print("DNN fallback will be disabled until model files are present.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
