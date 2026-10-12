"""Download and preview serving routes for Ratio Studio."""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from services.validator import validate_session_id
from services.image_processor import get_image_session_dirs
from services.zip_generator import create_zip_archive, create_multi_session_zip_archive
from services.crop_engine import RATIO_CONFIGS, resolve_ratio_config

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/preview/{image_id}/{ratio}")
async def get_preview_thumbnail(
    image_id: str,
    ratio: str,
    mode: Optional[str] = Query(default=None, description="smart_crop or safe_fit"),
    v: Optional[int] = Query(default=None, description="Revision version tag")
):
    """
    Serve the optimized high-fidelity thumbnail for fast preview.
    Falls back to the full resolution generated image if thumbnail is absent.
    Respects version tag for stable cache control.
    """
    validate_session_id(image_id)
    config = resolve_ratio_config(ratio)
    keys_to_check = [ratio.replace(":", "x")]
    if config:
        keys_to_check = [config["safe_key"], config["legacy_key"], ratio.replace(":", "x")]

    _, gen_session_dir = get_image_session_dirs(image_id)
    if not os.path.exists(gen_session_dir):
        raise HTTPException(status_code=404, detail="Session generated files not found.")

    headers = {"Cache-Control": "public, max-age=31536000, immutable"} if v is not None else {"Cache-Control": "no-cache"}

    # 1. Try mode-specific webp thumbnail first
    if mode:
        for k in keys_to_check:
            thumb_path = os.path.join(gen_session_dir, f"thumb_{k}_{mode}.webp")
            if os.path.exists(thumb_path):
                return FileResponse(thumb_path, media_type="image/webp", headers=headers)
        for k in keys_to_check:
            for ext, m_type in [("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")]:
                full_path = os.path.join(gen_session_dir, f"image_{k}_{mode}.{ext}")
                if os.path.exists(full_path):
                    return FileResponse(full_path, media_type=m_type, headers=headers)

    # 2. Try general webp thumbnails
    for k in keys_to_check:
        thumb_path = os.path.join(gen_session_dir, f"thumb_{k}.webp")
        if os.path.exists(thumb_path):
            return FileResponse(thumb_path, media_type="image/webp", headers=headers)

    # 3. Try general full images
    for k in keys_to_check:
        for ext, m_type in [("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")]:
            full_path = os.path.join(gen_session_dir, f"image_{k}.{ext}")
            if os.path.exists(full_path):
                return FileResponse(full_path, media_type=m_type, headers=headers)

    raise HTTPException(status_code=404, detail=f"Preview not found for ratio {ratio}")


@router.get("/preview-full/{image_id}/{ratio}")
async def get_preview_full_resolution(
    image_id: str,
    ratio: str,
    mode: Optional[str] = Query(default=None),
    v: Optional[int] = Query(default=None)
):
    """
    Serve the full-resolution generated output image specifically for
    full-screen inspection and high-fidelity modal expansion.
    """
    validate_session_id(image_id)
    config = resolve_ratio_config(ratio)
    keys_to_check = [ratio.replace(":", "x")]
    if config:
        keys_to_check = [config["safe_key"], config["legacy_key"], ratio.replace(":", "x")]

    _, gen_session_dir = get_image_session_dirs(image_id)
    if not os.path.exists(gen_session_dir):
        raise HTTPException(status_code=404, detail="Session generated files not found.")

    headers = {"Cache-Control": "public, max-age=31536000, immutable"} if v is not None else {"Cache-Control": "no-cache"}

    if mode:
        for k in keys_to_check:
            for ext, m_type in [("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")]:
                full_path = os.path.join(gen_session_dir, f"image_{k}_{mode}.{ext}")
                if os.path.exists(full_path):
                    return FileResponse(full_path, media_type=m_type, headers=headers)

    for k in keys_to_check:
        for ext, m_type in [("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")]:
            full_path = os.path.join(gen_session_dir, f"image_{k}.{ext}")
            if os.path.exists(full_path):
                return FileResponse(full_path, media_type=m_type, headers=headers)

    raise HTTPException(status_code=404, detail=f"Full output not found for ratio {ratio}")


@router.get("/download/{image_id}/{ratio}")
async def download_single_image(
    image_id: str,
    ratio: str,
    mode: Optional[str] = Query(default=None)
):
    """
    Download the full-resolution output image with clean, standard descriptive filename.
    Never serves a thumbnail. Respects processing mode if specified.
    """
    validate_session_id(image_id)
    config = resolve_ratio_config(ratio)
    keys_to_check = [ratio.replace(":", "x")]
    canonical_safe_key = ratio.replace(":", "x")
    if config:
        keys_to_check = [config["safe_key"], config["legacy_key"], ratio.replace(":", "x")]
        canonical_safe_key = config["safe_key"]

    _, gen_session_dir = get_image_session_dirs(image_id)
    if not os.path.exists(gen_session_dir):
        raise HTTPException(status_code=404, detail="Session generated files not found.")

    target_file = None
    target_ext = None

    if mode:
        for k in keys_to_check:
            for ext in ["jpg", "jpeg", "png", "webp"]:
                candidate = os.path.join(gen_session_dir, f"image_{k}_{mode}.{ext}")
                if os.path.exists(candidate):
                    target_file = candidate
                    target_ext = ext
                    break
            if target_file:
                break

    if not target_file:
        for k in keys_to_check:
            for ext in ["jpg", "jpeg", "png", "webp"]:
                candidate = os.path.join(gen_session_dir, f"image_{k}.{ext}")
                if os.path.exists(candidate):
                    target_file = candidate
                    target_ext = ext
                    break
            if target_file:
                break

    if not target_file:
        raise HTTPException(status_code=404, detail=f"Output for ratio {ratio} not found.")

    download_filename = f"image_{canonical_safe_key}.{target_ext}"
    media_type = f"image/{target_ext if target_ext != 'jpg' else 'jpeg'}"

    return FileResponse(
        target_file,
        media_type=media_type,
        filename=download_filename,
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'}
    )


@router.get("/download-all/{image_id}")
async def download_all_zip(
    image_id: str,
    mode: Optional[str] = Query(default=None)
):
    """
    Download all generated files as a ZIP archive named ratio-studio-images.zip,
    including a manifest.json with output dimensions and processing modes.
    """
    validate_session_id(image_id)
    try:
        zip_stream = create_zip_archive(image_id, mode=mode)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Generated output images not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate ZIP archive.")

    archive_filename = "ratio-studio-images.zip"
    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_filename}"'}
    )


@router.get("/download-batch")
async def download_batch_zip(
    image_ids: str = Query(..., description="Comma-separated image IDs"),
    mode: Optional[str] = Query(default=None)
):
    """
    Download a master ZIP archive containing ratio conversions for all specified images.
    Organizes each image's 5 outputs into their own subfolder.
    """
    ids = [i.strip() for i in image_ids.split(",") if i.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="No image IDs specified.")

    for i in ids:
        validate_session_id(i)

    try:
        zip_stream = create_multi_session_zip_archive(ids, mode=mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate batch archive: {str(e)}")

    archive_filename = f"ratio-studio-batch-{len(ids)}-images.zip"
    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_filename}"'}
    )

