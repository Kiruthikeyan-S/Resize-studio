"""File validation and security utilities for Ratio Studio."""

import os
import uuid
import re
from typing import Tuple, Dict, Any, List
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

SAFE_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
SAFE_RATIO_PATTERN = re.compile(r"^[a-zA-Z0-9_:]+$")
SAFE_HEX_COLOR_PATTERN = re.compile(r"^#?[a-fA-F0-9]{6}$")


def validate_file_size(file: UploadFile) -> None:
    """Validate that client-declared file size does not exceed maximum upload size."""
    if hasattr(file, "size") and file.size is not None:
        if file.size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
            )


def validate_stream_bytes(data: bytes) -> None:
    """Validate that actual streamed byte length does not exceed maximum upload size."""
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded data ({len(data) / (1024 * 1024):.1f}MB) exceeds 20MB limit."
        )


def validate_session_id(image_id: str) -> None:
    """Validate that image_id is a valid hex uuid to prevent path traversal."""
    clean = str(image_id).strip().lower()
    if not SAFE_ID_PATTERN.match(clean):
        raise HTTPException(status_code=400, detail="Invalid session identifier format.")


def validate_hex_color(hex_str: str) -> str:
    """Validate hexadecimal background color string."""
    clean = hex_str.strip()
    if not SAFE_HEX_COLOR_PATTERN.match(clean):
        raise HTTPException(
            status_code=422,
            detail="Invalid background color. Must be a 6-character hex code (e.g. #FFFFFF)."
        )
    return clean if clean.startswith("#") else f"#{clean}"


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
            status_code=413,
            detail=f"File size ({file_size / (1024 * 1024):.1f}MB) exceeds 20MB limit."
        )

    try:
        with Image.open(file_path) as img:
            format_name = (img.format or "").upper()
            if format_name not in ["JPEG", "PNG", "WEBP"]:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported image format: {format_name}. Only JPEG, PNG, and WebP are supported."
                )

            width, height = img.size
            total_pixels = width * height
            if total_pixels > MAX_DECODED_PIXELS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Image resolution ({width}x{height}) is too large (max {MAX_DECODED_PIXELS} pixels)."
                )

            if width < 10 or height < 10:
                raise HTTPException(
                    status_code=422,
                    detail="Image dimensions are too small (minimum 10x10 pixels)."
                )

            img.verify()

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
        raise HTTPException(status_code=422, detail="Corrupted or unreadable image file.")


def generate_safe_id() -> str:
    """Generate a clean random 32-character hexadecimal UUID string."""
    return uuid.uuid4().hex


def sanitize_filename(filename: str) -> str:
    """Remove unsafe characters and path traversal attempts from filenames."""
    basename = os.path.basename(filename)
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", basename)
    return clean[:100] if clean else "image.jpg"
