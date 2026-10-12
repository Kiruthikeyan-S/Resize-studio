"""Download and preview serving routes for Ratio Studio."""

import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from services.image_processor import get_image_session_dirs
from services.zip_generator import create_zip_archive
from services.crop_engine import RATIO_CONFIGS, resolve_ratio_config

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/preview/{image_id}/{ratio}")
async def get_preview_thumbnail(image_id: str, ratio: str):
    """
    Serve the optimized thumbnail for instant, lightweight frontend preview.
    Falls back to the full resolution generated image if thumbnail is absent.
    """
    config = resolve_ratio_config(ratio)
    keys_to_check = [ratio.replace(":", "x")]
    if config:
        keys_to_check = [config["safe_key"], config["legacy_key"], ratio.replace(":", "x")]

    _, gen_session_dir = get_image_session_dirs(image_id)
    if not os.path.exists(gen_session_dir):
        raise HTTPException(status_code=404, detail="Session generated files not found.")

    # 1. Try webp thumbnails
    for k in keys_to_check:
        thumb_path = os.path.join(gen_session_dir, f"thumb_{k}.webp")
        if os.path.exists(thumb_path):
            return FileResponse(thumb_path, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})

    # 2. Try full images
    for k in keys_to_check:
        for ext, m_type in [("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")]:
            full_path = os.path.join(gen_session_dir, f"image_{k}.{ext}")
            if os.path.exists(full_path):
                return FileResponse(full_path, media_type=m_type)

    raise HTTPException(status_code=404, detail=f"Preview not found for ratio {ratio}")


@router.get("/download/{image_id}/{ratio}")
async def download_single_image(image_id: str, ratio: str):
    """
    Download an individual output image with clean, standard descriptive filename.
    e.g. image_square_1x1.jpg, image_landscape_16x9.jpg
    """
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
async def download_all_zip(image_id: str):
    """
    Download all generated files as a ZIP archive named ratio-studio-images.zip,
    including a manifest.json with output dimensions and processing modes.
    """
    try:
        zip_stream = create_zip_archive(image_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Generated output images not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate ZIP archive: {str(e)}")

    archive_filename = "ratio-studio-images.zip"

    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{archive_filename}"'}
    )
