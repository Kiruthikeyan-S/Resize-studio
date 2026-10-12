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
    get_raw_file_path,
    get_original_metadata,
    update_working_image,
    reset_working_image,
    cleanup_old_sessions,
)

from typing import List, Optional
from pydantic import Field

router = APIRouter(prefix="/api", tags=["upload"])


class UploadResponse(BaseModel):
    image_id: str
    original_filename: str
    width: int
    height: int
    raw_width: Optional[int] = None
    raw_height: Optional[int] = None
    file_size: int
    format: str
    mode: str
    original_url: str
    raw_url: Optional[str] = None
    version: int = 1
    is_low_res: bool = False
    is_cropped_master: bool = False
    master_crop_box: Optional[List[int]] = None


class UpdateOriginalRequest(BaseModel):
    image_id: str
    crop_box: List[int]  # [left, top, right, bottom]


async def _process_single_upload(file: UploadFile) -> UploadResponse:
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
        raw_width=meta.get("raw_width", meta["width"]),
        raw_height=meta.get("raw_height", meta["height"]),
        file_size=meta["file_size"],
        format=meta["format"],
        mode=meta["mode"],
        original_url=f"/api/original/{image_id}?v={meta.get('version', 1)}",
        raw_url=f"/api/raw/{image_id}",
        version=meta.get("version", 1),
        is_low_res=meta.get("is_low_res", False),
        is_cropped_master=meta.get("is_cropped_master", False),
        master_crop_box=meta.get("master_crop_box"),
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Accept and validate a single image upload."""
    cleanup_old_sessions(max_age_seconds=3600)
    return await _process_single_upload(file)


@router.post("/upload-multiple", response_model=List[UploadResponse])
async def upload_multiple_images(files: List[UploadFile] = File(...)):
    """Accept and validate multiple image uploads in batch."""
    if not files:
        raise HTTPException(status_code=400, detail="No files selected.")

    cleanup_old_sessions(max_age_seconds=3600)
    results: List[UploadResponse] = []
    errors: List[str] = []

    for f in files:
        if not f.filename:
            continue
        try:
            res = await _process_single_upload(f)
            results.append(res)
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            errors.append(f"{f.filename}: {detail}")

    if not results and errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    return results


@router.get("/raw/{image_id}")
async def get_raw_original(image_id: str):
    """Serve the untouched original upload without any working transforms."""
    validate_session_id(image_id)
    raw_path = get_raw_file_path(image_id)
    if not raw_path or not os.path.exists(raw_path):
        raise HTTPException(status_code=404, detail="Raw original image not found.")

    ext = os.path.splitext(raw_path)[1].lower().lstrip(".")
    m_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
    return FileResponse(raw_path, media_type=m_type)


@router.get("/original/{image_id}")
async def get_original(image_id: str):
    """Serve the working master image for preview and crop adjustments."""
    validate_session_id(image_id)
    file_path = get_original_file_path(image_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original image not found.")

    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    m_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
    # Disallow browser caching on working master to ensure live updates reflect immediately
    return FileResponse(file_path, media_type=m_type, headers={"Cache-Control": "no-cache"})


@router.post("/update-original", response_model=UploadResponse)
async def update_original_framing(payload: UpdateOriginalRequest):
    """
    Apply user-adjusted framing (pan/zoom crop box) to create the new finalized working copy.
    The untouched original is preserved so the user can re-edit or reset anytime.
    """
    validate_session_id(payload.image_id)
    if len(payload.crop_box) != 4:
        raise HTTPException(status_code=422, detail="crop_box must contain 4 integers [left, top, right, bottom]")

    crop_tuple = (payload.crop_box[0], payload.crop_box[1], payload.crop_box[2], payload.crop_box[3])
    try:
        updated_meta = update_working_image(payload.image_id, crop_tuple)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image session not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update original framing: {str(e)}")

    return UploadResponse(
        image_id=payload.image_id,
        original_filename=updated_meta["original_filename"],
        width=updated_meta["width"],
        height=updated_meta["height"],
        raw_width=updated_meta.get("raw_width", updated_meta["width"]),
        raw_height=updated_meta.get("raw_height", updated_meta["height"]),
        file_size=updated_meta["file_size"],
        format=updated_meta["format"],
        mode=updated_meta["mode"],
        original_url=f"/api/original/{payload.image_id}?v={updated_meta.get('version', 1)}",
        raw_url=f"/api/raw/{payload.image_id}",
        version=updated_meta.get("version", 1),
        is_low_res=updated_meta.get("is_low_res", False),
        is_cropped_master=updated_meta.get("is_cropped_master", True),
        master_crop_box=updated_meta.get("master_crop_box"),
    )


@router.post("/reset-original/{image_id}", response_model=UploadResponse)
async def reset_original_framing(image_id: str):
    """
    Reset the working image back to the untouched raw upload.
    """
    validate_session_id(image_id)
    try:
        reset_meta = reset_working_image(image_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image session not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset original framing: {str(e)}")

    return UploadResponse(
        image_id=image_id,
        original_filename=reset_meta["original_filename"],
        width=reset_meta["width"],
        height=reset_meta["height"],
        raw_width=reset_meta.get("raw_width", reset_meta["width"]),
        raw_height=reset_meta.get("raw_height", reset_meta["height"]),
        file_size=reset_meta["file_size"],
        format=reset_meta["format"],
        mode=reset_meta["mode"],
        original_url=f"/api/original/{image_id}?v={reset_meta.get('version', 1)}",
        raw_url=f"/api/raw/{image_id}",
        version=reset_meta.get("version", 1),
        is_low_res=reset_meta.get("is_low_res", False),
        is_cropped_master=False,
        master_crop_box=None,
    )
