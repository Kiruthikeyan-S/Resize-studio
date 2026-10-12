"""Upload route for Ratio Studio."""

import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.validator import (
    validate_file_size,
    validate_image_content,
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
    Validates MIME type, file size, and actual image content using Pillow.
    Returns safe image_id and original metadata.
    """
    # Trigger opportunistic cleanup of expired temporary sessions
    cleanup_old_sessions(max_age_seconds=3600)

    # Basic file check
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    validate_file_size(file)

    # Read bytes
    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload stream: {str(e)}")

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    image_id = generate_safe_id()
    clean_filename = sanitize_filename(file.filename)
    raw_ext = os.path.splitext(clean_filename)[1].lower()
    if raw_ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raw_ext = ".jpg"

    # Save and validate content
    try:
        file_path, meta = save_original_image(
            image_id=image_id,
            file_bytes=contents,
            original_filename=clean_filename,
            extension=raw_ext
        )
        # Deep validation on actual written file
        content_info = validate_image_content(file_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid or corrupted image: {str(e)}")

    return UploadResponse(
        image_id=image_id,
        original_filename=meta["original_filename"],
        width=meta["width"],
        height=meta["height"],
        file_size=meta["file_size"],
        format=content_info["format"],
        mode=content_info["mode"],
        original_url=f"/api/original/{image_id}",
    )


@router.get("/original/{image_id}")
async def get_original(image_id: str):
    """Serve the original image for preview and crop adjustments."""
    file_path = get_original_file_path(image_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original image not found.")

    ext = os.path.splitext(file_path)[1].lower()
    media_type = "image/jpeg"
    if ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"

    return FileResponse(file_path, media_type=media_type)
