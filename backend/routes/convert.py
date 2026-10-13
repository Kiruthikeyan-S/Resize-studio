"""Conversion and crop adjustment routes for Ratio Studio."""

import os
import json
from typing import Optional, Dict, List, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.validator import (
    validate_file_size,
    validate_stream_bytes,
    validate_image_content,
    validate_session_id,
    validate_hex_color,
    sanitize_filename,
)
from services.image_processor import (
    generate_all_ratios,
    regenerate_single_ratio,
    delete_session,
    get_image_session_dirs,
    get_original_metadata,
    get_ratio_source_info,
)
from services.crop_engine import RATIO_CONFIGS, resolve_ratio_config
from services.groq_vision import analyze_image_with_groq, is_groq_enabled

router = APIRouter(prefix="/api", tags=["convert"])


class ConvertRequest(BaseModel):
    image_id: str
    mode: str = Field(default="safe_fit", description="safe_fit: preserve the complete approved crop")
    export_format: str = Field(default="jpeg", description="jpeg, png, or webp")
    quality: int = Field(default=90, ge=1, le=100)
    bg_color_hex: str = Field(default="#F8FAFC")
    is_transparent: bool = Field(default=False)
    sharpen: bool = Field(default=False)
    denoise: bool = Field(default=False)
    custom_crops: Optional[Dict[str, List[int]]] = None


class FitInfoItem(BaseModel):
    has_subject_box: bool
    fits_completely: bool
    clipped_horizontal: bool
    clipped_vertical: bool
    message: str


class VariantItem(BaseModel):
    selection_id: str
    ratio_safe_key: str
    ratio_name: str
    size_key: str
    size_label: str
    width: int
    height: int
    file_name: str
    file_size: int


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
    version: int
    preview_url: str
    download_url: str
    source_url: str
    source_width: int
    source_height: int
    crop_box: List[int]
    mode: str
    edges_trimmed: Optional[bool] = False
    fit_info: Optional[FitInfoItem] = None
    fallback_reason: Optional[str] = None
    variants: List[VariantItem] = []


class ConvertResponse(BaseModel):
    image_id: str
    original_filename: str
    export_format: str
    mode: str
    revision: int = 0
    outputs: List[OutputRatioItem]


class AdjustCropRequest(BaseModel):
    image_id: str
    ratio: str
    crop_box: List[int]  # [left, top, right, bottom]


@router.post("/convert", response_model=ConvertResponse)
async def convert_image(payload: ConvertRequest):
    """
    Generate all 5 predefined aspect ratios for the uploaded image.
    Option A: Smart Crop (Professional full-frame crop, subject-centered, no blurred backgrounds).
    Option B: Safe Fit (Complete image preserved on clean solid studio background).
    Option C: AI Background Expansion (Product-safe outpainting, zero pixel alteration).
    """
    validate_session_id(payload.image_id)

    valid_modes = ["safe_fit", "fit_contain", "smart_fit", "smart_crop", "manual_crop", "ai_expand"]
    mode = payload.mode if payload.mode in valid_modes else "safe_fit"

    valid_formats = ["jpeg", "png", "webp"]
    export_format = payload.export_format.lower() if payload.export_format.lower() in valid_formats else "jpeg"
    bg_hex = validate_hex_color(payload.bg_color_hex) if not payload.is_transparent else payload.bg_color_hex

    custom_crops_dict = {}
    if payload.custom_crops:
        for k, coords in payload.custom_crops.items():
            if len(coords) == 4:
                custom_crops_dict[k] = (coords[0], coords[1], coords[2], coords[3])

    source_meta = get_original_metadata(payload.image_id) or {}
    if source_meta.get("is_cropped_master"):
        mode = "safe_fit"

    try:
        results = generate_all_ratios(
            image_id=payload.image_id,
            mode=mode,
            export_format=export_format,
            quality=payload.quality,
            bg_color_hex=bg_hex,
            is_transparent=payload.is_transparent,
            sharpen=payload.sharpen,
            denoise=payload.denoise,
            custom_crops=custom_crops_dict,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image session not found or expired.")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Image processing failed.")

    return ConvertResponse(
        image_id=results["image_id"],
        original_filename=results["original_filename"],
        export_format=results["export_format"],
        mode=results["mode"],
        revision=results.get("revision", 0),
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
    Maintains per-ratio source isolation in manifest.
    """
    validate_session_id(image_id)
    config = resolve_ratio_config(ratio)
    if not config:
        raise HTTPException(status_code=400, detail=f"Invalid ratio identifier: {ratio}")

    safe_key = config["safe_key"]

    source_path = None
    if file is not None and file.filename:
        validate_file_size(file)
        contents = await file.read()
        validate_stream_bytes(contents)
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
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update ratio.")

    return updated_output


@router.post("/adjust-crop")
async def adjust_crop(payload: AdjustCropRequest):
    """
    Adjust crop coordinates for an existing ratio output.
    Validates crop coordinates and aspect ratio before processing.
    """
    validate_session_id(payload.image_id)
    config = resolve_ratio_config(payload.ratio)
    if not config:
        raise HTTPException(status_code=400, detail=f"Invalid ratio identifier: {payload.ratio}")

    if len(payload.crop_box) != 4:
        raise HTTPException(status_code=422, detail="crop_box must contain 4 integers [left, top, right, bottom]")

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
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update crop.")

    return updated_output


@router.get("/ratio-source/{image_id}/{ratio}")
async def get_ratio_source_image(image_id: str, ratio: str):
    """
    Serve the active source image for a given ratio (used by CropEditor).
    If an individual replacement was uploaded, serves that file; otherwise master original.
    """
    validate_session_id(image_id)
    config = resolve_ratio_config(ratio)
    if not config:
        raise HTTPException(status_code=400, detail=f"Invalid ratio identifier: {ratio}")

    source_path, _, _, _ = get_ratio_source_info(image_id, config["safe_key"])
    if not source_path or not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source image not found.")

    ext = os.path.splitext(source_path)[1].lower().lstrip(".")
    m_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
    return FileResponse(source_path, media_type=m_type)


@router.get("/analyze/{image_id}")
async def analyze_image(image_id: str):
    """
    Optional analysis service using Groq Vision API.
    Returns subject guidance and crop risk factors, or status disabled.
    """
    validate_session_id(image_id)
    source_path, _, _, _ = get_ratio_source_info(image_id, "square_1x1")
    if not source_path or not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Image session not found.")

    if not is_groq_enabled():
        return {
            "enabled": False,
            "message": "Groq Vision analysis is optional and currently disabled (no API key configured)."
        }

    analysis = analyze_image_with_groq(source_path)
    if not analysis:
        return {
            "enabled": True,
            "available": False,
            "message": "Groq Vision analysis is momentarily unavailable. Continuing with standard DSP framing."
        }

    return {
        "enabled": True,
        "available": True,
        "analysis": analysis.dict()
    }


@router.delete("/images/{image_id}")
async def delete_image_session(image_id: str):
    """Delete temporary input and output files for the session."""
    validate_session_id(image_id)
    success = delete_session(image_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or already deleted.")
    return {"status": "success", "message": f"Session {image_id} deleted."}
