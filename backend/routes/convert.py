"""Conversion and crop adjustment routes for Ratio Studio."""

import os
import json
from typing import Optional, Dict, List, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field

from services.validator import validate_file_size, validate_image_content, sanitize_filename
from services.image_processor import (
    generate_all_ratios,
    regenerate_single_ratio,
    delete_session,
    get_image_session_dirs,
    get_original_metadata,
)
from services.crop_engine import RATIO_CONFIGS, resolve_ratio_config

router = APIRouter(prefix="/api", tags=["convert"])


class ConvertRequest(BaseModel):
    image_id: str
    mode: str = Field(default="smart_crop", description="smart_crop, safe_fit, or manual_crop")
    export_format: str = Field(default="jpeg", description="jpeg, png, or webp")
    quality: int = Field(default=90, ge=1, le=100)
    bg_color_hex: str = Field(default="#18181B")
    is_transparent: bool = Field(default=False)
    sharpen: bool = Field(default=False)
    denoise: bool = Field(default=False)
    custom_crops: Optional[Dict[str, List[int]]] = None


class OutputRatioItem(BaseModel):
    ratio_key: str
    safe_key: str
    legacy_key: Optional[str] = None
    name: str
    width: int
    height: int
    orientation: str
    file_name: str
    file_size: int
    preview_url: str
    download_url: str
    crop_box: List[int]
    mode: str
    edges_trimmed: Optional[bool] = False


class ConvertResponse(BaseModel):
    image_id: str
    original_filename: str
    export_format: str
    mode: str
    outputs: List[OutputRatioItem]


class AdjustCropRequest(BaseModel):
    image_id: str
    ratio: str
    crop_box: List[int]  # [left, top, right, bottom]


@router.post("/convert", response_model=ConvertResponse)
async def convert_image(payload: ConvertRequest):
    """
    Generate all 5 predefined aspect ratios for the uploaded image.
    Default mode: Smart Crop (Professional full-frame crop, subject-centered, no blurred backgrounds).
    Alternative mode: Safe Fit (Complete image preserved on clean solid background).
    """
    valid_modes = ["smart_crop", "safe_fit", "manual_crop", "fit_contain", "smart_fit"]
    mode = payload.mode if payload.mode in valid_modes else "smart_crop"

    valid_formats = ["jpeg", "png", "webp"]
    export_format = payload.export_format.lower() if payload.export_format.lower() in valid_formats else "jpeg"

    custom_crops_dict = {}
    if payload.custom_crops:
        for k, coords in payload.custom_crops.items():
            if len(coords) == 4:
                custom_crops_dict[k] = (coords[0], coords[1], coords[2], coords[3])

    try:
        results = generate_all_ratios(
            image_id=payload.image_id,
            mode=mode,
            export_format=export_format,
            quality=payload.quality,
            bg_color_hex=payload.bg_color_hex,
            is_transparent=payload.is_transparent,
            sharpen=payload.sharpen,
            denoise=payload.denoise,
            custom_crops=custom_crops_dict,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image session not found or expired.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image processing error: {str(e)}")

    return ConvertResponse(
        image_id=results["image_id"],
        original_filename=results["original_filename"],
        export_format=results["export_format"],
        mode=results["mode"],
        outputs=results["outputs"],
    )


@router.post("/replace/{ratio}")
async def replace_ratio(
    ratio: str,
    image_id: str = Form(...),
    file: Optional[UploadFile] = File(None),
    mode: Optional[str] = Form(None),
    crop_coords: Optional[str] = Form(None),
):
    """
    Replace or reprocess only one selected ratio without altering the other four outputs.
    """
    config = resolve_ratio_config(ratio)
    if not config:
        raise HTTPException(status_code=400, detail=f"Invalid ratio identifier: {ratio}")

    safe_key = config["safe_key"]

    source_path = None
    if file is not None and file.filename:
        validate_file_size(file)
        contents = await file.read()
        if len(contents) > 0:
            orig_dir, _ = get_image_session_dirs(image_id)
            clean_name = sanitize_filename(file.filename)
            ext = os.path.splitext(clean_name)[1].lower() or ".jpg"
            source_path = os.path.join(orig_dir, f"replace_{safe_key}{ext}")
            with open(source_path, "wb") as f:
                f.write(contents)
            validate_image_content(source_path)

    manual_crop = None
    if crop_coords:
        try:
            parsed = json.loads(crop_coords)
            if isinstance(parsed, list) and len(parsed) == 4:
                manual_crop = (int(parsed[0]), int(parsed[1]), int(parsed[2]), int(parsed[3]))
        except Exception:
            pass

    try:
        updated_output = regenerate_single_ratio(
            image_id=image_id,
            ratio_safe_key=safe_key,
            source_image_path=source_path,
            mode=mode,
            manual_crop=manual_crop,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image session not found or expired.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ratio: {str(e)}")

    return updated_output


@router.post("/adjust-crop")
async def adjust_crop(payload: AdjustCropRequest):
    """
    Adjust crop coordinates for an existing ratio output.
    """
    config = resolve_ratio_config(payload.ratio)
    if not config:
        raise HTTPException(status_code=400, detail=f"Invalid ratio identifier: {payload.ratio}")

    if len(payload.crop_box) != 4:
        raise HTTPException(status_code=400, detail="crop_box must contain 4 integers [left, top, right, bottom]")

    crop_tuple = (payload.crop_box[0], payload.crop_box[1], payload.crop_box[2], payload.crop_box[3])

    try:
        updated_output = regenerate_single_ratio(
            image_id=payload.image_id,
            ratio_safe_key=config["safe_key"],
            mode="manual_crop",
            manual_crop=crop_tuple,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image session not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update crop: {str(e)}")

    return updated_output


@router.delete("/images/{image_id}")
async def delete_image_session(image_id: str):
    """Delete temporary input and output files for the session."""
    success = delete_session(image_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or already deleted.")
    return {"status": "success", "message": f"Session {image_id} deleted."}
