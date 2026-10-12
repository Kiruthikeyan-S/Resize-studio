"""Upload route for Ratio Studio."""

import os
import io
from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.validator import (
    validate_file_size,
    validate_stream_bytes,
    validate_image_content,
    validate_session_id,
    generate_safe_id,
    sanitize_filename,
    ALLOWED_MIME_TYPES,
)
from services.image_processor import (
    save_original_image,
    get_original_file_path,
    get_original_metadata,
    cleanup_old_sessions,
)

router = APIRouter(prefix="/api", tags=["upload"])


class UploadResponse(BaseModel):
    image_id: str
    original_filename: str
    width: int
    height: int
    file_size: int
    format: str
    mode: str
    original_url: str


@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    Accept and validate an image upload.
    Validates MIME type, file size during streaming, and actual image content using Pillow.
    Returns safe image_id and original metadata.
    """
    cleanup_old_sessions(max_age_seconds=3600)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    validate_file_size(file)

    try:
        contents = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read upload stream.")

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    validate_stream_bytes(contents)

    image_id = generate_safe_id()
    clean_filename = sanitize_filename(file.filename)
    raw_ext = os.path.splitext(clean_filename)[1].lower()
    if raw_ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raw_ext = ".jpg"

    # Validate image bytes in memory first (catches corrupt/unsupported images safely)
    try:
        from io import BytesIO
        with Image.open(BytesIO(contents)) as test_img:
            fmt = (test_img.format or "").upper()
            if fmt not in ["JPEG", "PNG", "WEBP"]:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported image format: {fmt}. Only JPEG, PNG, and WebP are supported."
                )
            w, h = test_img.size
            if (w * h) > 64_000_000:
                raise HTTPException(status_code=422, detail="Image pixel resolution exceeds limit.")
            if w < 10 or h < 10:
                raise HTTPException(status_code=422, detail="Image dimensions are too small (minimum 10x10).")
            test_img.verify()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Corrupted or invalid image file.")

    # Save original untouched and create working copy
    file_path, meta = save_original_image(
        image_id=image_id,
        file_bytes=contents,
        original_filename=clean_filename,
        extension=raw_ext
    )

    return UploadResponse(
        image_id=image_id,
        original_filename=meta["original_filename"],
        width=meta["width"],
        height=meta["height"],
        file_size=meta["file_size"],
        format=meta["format"],
        mode=meta["mode"],
        original_url=f"/api/original/{image_id}",
    )


@router.get("/original/{image_id}")
async def get_original(image_id: str):
    """Serve the working master image for preview and crop adjustments."""
    validate_session_id(image_id)
    file_path = get_original_file_path(image_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original image not found.")

    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    m_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
    return FileResponse(file_path, media_type=m_type)
