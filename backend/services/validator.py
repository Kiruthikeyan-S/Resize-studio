"""File validation and security utilities for Ratio Studio."""

import os
import uuid
import re
from typing import Tuple, Dict, Any
from fastapi import UploadFile, HTTPException
from PIL import Image

# Configurable limits
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_DECODED_PIXELS = 64_000_000     # ~8000x8000 max image resolution (decompression bomb protection)
Image.MAX_IMAGE_PIXELS = MAX_DECODED_PIXELS

ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

SAFE_RATIO_PATTERN = re.compile(r"^[0-9]+x[0-9]+$|^[0-9]+_[0-9]+$|^[0-9]+:[0-9]+$")


def validate_file_size(file: UploadFile) -> None:
    """Validate that the file does not exceed maximum upload size."""
    if hasattr(file, "size") and file.size is not None:
        if file.size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
            )


def validate_image_content(file_path: str) -> Dict[str, Any]:
    """
    Validate actual file contents using Pillow.
    Ensures file is a valid image, within dimensions and pixel limits,
    and returns its metadata.
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Uploaded file not found.")

    file_size = os.path.getsize(file_path)
    if file_size > MAX_UPLOAD_SIZE:
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail=f"File size ({file_size / (1024 * 1024):.1f}MB) exceeds 20MB limit."
        )

    try:
        with Image.open(file_path) as img:
            # Check format
            format_name = (img.format or "").upper()
            if format_name not in ["JPEG", "PNG", "WEBP"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported image format: {format_name}. Only JPEG, PNG, and WebP are supported."
                )

            # Check pixel dimensions
            width, height = img.size
            total_pixels = width * height
            if total_pixels > MAX_DECODED_PIXELS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image resolution ({width}x{height}) is too large (max {MAX_DECODED_PIXELS} pixels)."
                )

            if width < 10 or height < 10:
                raise HTTPException(
                    status_code=400,
                    detail="Image dimensions are too small (minimum 10x10 pixels)."
                )

            # Pillow verify checks file integrity without full decode
            img.verify()

        # Re-open to read color mode and details (since verify closes the image or invalidates state)
        with Image.open(file_path) as img:
            color_mode = img.mode
            width, height = img.size

        return {
            "format": format_name,
            "width": width,
            "height": height,
            "file_size": file_size,
            "mode": color_mode,
        }

    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail=f"Corrupted or invalid image file: {str(e)}"
        )


def generate_safe_id() -> str:
    """Generate a collision-free, safe image ID."""
    return uuid.uuid4().hex


def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters to prevent path traversal."""
    basename = os.path.basename(filename)
    # Only keep alphanumeric, dash, underscore, dot
    clean_name = re.sub(r"[^\w\.-]", "_", basename)
    return clean_name or "uploaded_image"
