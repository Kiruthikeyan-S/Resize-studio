"""Image processor pipeline integrating validation, Professional Smart Crop, Safe Fit, and quality management."""

import os
import json
import time
import shutil
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

from services.crop_engine import (
    RATIO_CONFIGS,
    resolve_ratio_config,
    process_image_for_ratio,
    calculate_crop_window,
    detect_saliency_center,
)
from services.quality_manager import (
    fix_exif_orientation,
    ensure_srgb_profile,
    handle_alpha_transparency,
    apply_mild_sharpening,
    apply_mild_denoising,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
ORIGINAL_DIR = os.path.join(STORAGE_DIR, "original")
GENERATED_DIR = os.path.join(STORAGE_DIR, "generated")

os.makedirs(ORIGINAL_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)


def get_image_session_dirs(image_id: str) -> Tuple[str, str]:
    """Get secure directories for an image session."""
    orig_session_dir = os.path.join(ORIGINAL_DIR, image_id)
    gen_session_dir = os.path.join(GENERATED_DIR, image_id)
    return orig_session_dir, gen_session_dir


def cleanup_old_sessions(max_age_seconds: int = 3600) -> None:
    """Clean up image directories older than max_age_seconds (default 1 hour)."""
    now = time.time()
    for base in [ORIGINAL_DIR, GENERATED_DIR]:
        if not os.path.exists(base):
            continue
        for item in os.listdir(base):
            item_path = os.path.join(base, item)
            if os.path.isdir(item_path):
                try:
                    mtime = os.path.getmtime(item_path)
                    if now - mtime > max_age_seconds:
                        shutil.rmtree(item_path, ignore_errors=True)
                except Exception:
                    pass


def delete_session(image_id: str) -> bool:
    """Delete all files associated with an image_id."""
    orig_dir, gen_dir = get_image_session_dirs(image_id)
    removed = False
    if os.path.exists(orig_dir):
        shutil.rmtree(orig_dir, ignore_errors=True)
        removed = True
    if os.path.exists(gen_dir):
        shutil.rmtree(gen_dir, ignore_errors=True)
        removed = True
    return removed


def save_original_image(
    image_id: str,
    file_bytes: bytes,
    original_filename: str,
    extension: str
) -> Tuple[str, Dict[str, Any]]:
    """
    Save uploaded original image file, apply EXIF rotation, and extract metadata.
    """
    orig_session_dir, _ = get_image_session_dirs(image_id)
    os.makedirs(orig_session_dir, exist_ok=True)

    file_path = os.path.join(orig_session_dir, f"original{extension}")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    with Image.open(file_path) as img:
        img_fixed = fix_exif_orientation(img)
        img_fixed = ensure_srgb_profile(img_fixed)
        width, height = img_fixed.size
        mode = img_fixed.mode
        format_name = (img.format or extension.lstrip(".")).upper()
        img_fixed.save(file_path, format=img.format or "JPEG", quality=95)

    meta = {
        "image_id": image_id,
        "original_filename": original_filename,
        "width": width,
        "height": height,
        "file_size": os.path.getsize(file_path),
        "format": format_name,
        "mode": mode,
        "file_path": file_path,
        "created_at": time.time(),
        "is_low_res": width < 1600 or height < 1200,
    }

    meta_path = os.path.join(orig_session_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return file_path, meta


def get_original_metadata(image_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve original image metadata."""
    orig_session_dir, _ = get_image_session_dirs(image_id)
    meta_path = os.path.join(orig_session_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_original_file_path(image_id: str) -> Optional[str]:
    """Retrieve original image file path."""
    meta = get_original_metadata(image_id)
    if meta and "file_path" in meta and os.path.exists(meta["file_path"]):
        return meta["file_path"]
    return None


def generate_all_ratios(
    image_id: str,
    mode: str = "smart_crop",
    export_format: str = "jpeg",
    quality: int = 90,
    bg_color_hex: str = "#18181B",
    is_transparent: bool = False,
    sharpen: bool = False,
    denoise: bool = False,
    custom_crops: Optional[Dict[str, Tuple[int, int, int, int]]] = None
) -> Dict[str, Any]:
    """
    Generate all 5 predefined aspect ratio images.
    Default mode: 'smart_crop' (Professional full-frame crop, subject-centered, no blur).
    Alternative mode: 'safe_fit' (Preserves full image with clean solid background).
    """
    orig_path = get_original_file_path(image_id)
    if not orig_path:
        raise FileNotFoundError(f"Original image not found for session {image_id}")

    orig_meta = get_original_metadata(image_id) or {}
    _, gen_session_dir = get_image_session_dirs(image_id)
    os.makedirs(gen_session_dir, exist_ok=True)

    export_format = export_format.lower()
    if export_format not in ["jpeg", "png", "webp"]:
        export_format = "jpeg"
    ext = "jpg" if export_format == "jpeg" else export_format

    custom_crops = custom_crops or {}

    results = []
    with Image.open(orig_path) as source_img:
        source_img = ensure_srgb_profile(source_img)
        orig_w, orig_h = source_img.size

        for ratio_key, config in RATIO_CONFIGS.items():
            safe_key = config["safe_key"]
            legacy_key = config["legacy_key"]
            manual_crop = custom_crops.get(ratio_key) or custom_crops.get(safe_key) or custom_crops.get(legacy_key)

            processed, crop_box = process_image_for_ratio(
                img=source_img,
                target_config=config,
                mode=mode,
                bg_color_hex=bg_color_hex,
                is_transparent=is_transparent,
                manual_crop=manual_crop
            )

            if sharpen:
                processed = apply_mild_sharpening(processed)
            if denoise:
                processed = apply_mild_denoising(processed)

            # Transparency handling
            if is_transparent and export_format in ["png", "webp"]:
                final_img = processed.convert("RGBA")
            else:
                final_img = handle_alpha_transparency(
                    processed,
                    target_format=export_format,
                    bg_color_hex=bg_color_hex
                )

            # Primary file name
            out_filename = f"image_{safe_key}.{ext}"
            out_path = os.path.join(gen_session_dir, out_filename)

            # Save full resolution output
            save_kwargs = {}
            if export_format in ["jpeg", "webp"]:
                save_kwargs["quality"] = max(1, min(100, quality))
            if export_format == "png":
                save_kwargs["compress_level"] = 6
            final_img.save(out_path, format=export_format.upper(), **save_kwargs)

            # Legacy alias copy (e.g. image_1x1.jpg)
            legacy_filename = f"image_{legacy_key}.{ext}"
            legacy_path = os.path.join(gen_session_dir, legacy_filename)
            if legacy_path != out_path:
                shutil.copyfile(out_path, legacy_path)

            # Optimized preview thumbnail (max 600px)
            thumb_scale = min(600 / config["width"], 600 / config["height"], 1.0)
            thumb_w = int(round(config["width"] * thumb_scale))
            thumb_h = int(round(config["height"] * thumb_scale))
            thumb_img = final_img.resize((thumb_w, thumb_h), resample=Image.Resampling.LANCZOS)

            thumb_filename = f"thumb_{safe_key}.webp"
            thumb_path = os.path.join(gen_session_dir, thumb_filename)
            thumb_img.save(thumb_path, format="WEBP", quality=82)

            legacy_thumb_path = os.path.join(gen_session_dir, f"thumb_{legacy_key}.webp")
            if legacy_thumb_path != thumb_path:
                shutil.copyfile(thumb_path, legacy_thumb_path)

            file_size = os.path.getsize(out_path)

            # Determine whether edge content was trimmed
            crop_w = crop_box[2] - crop_box[0]
            crop_h = crop_box[3] - crop_box[1]
            edges_trimmed = (crop_w < orig_w * 0.85) or (crop_h < orig_h * 0.85)

            results.append({
                "ratio_key": ratio_key,
                "safe_key": safe_key,
                "legacy_key": legacy_key,
                "name": config["name"],
                "width": config["width"],
                "height": config["height"],
                "orientation": config["orientation"],
                "file_name": out_filename,
                "file_size": file_size,
                "file_path": out_path,
                "preview_url": f"/api/preview/{image_id}/{safe_key}",
                "download_url": f"/api/download/{image_id}/{safe_key}",
                "crop_box": list(crop_box),
                "mode": mode,
                "edges_trimmed": edges_trimmed and mode == "smart_crop",
            })

    session_data = {
        "image_id": image_id,
        "original_filename": orig_meta.get("original_filename", "image"),
        "original_width": orig_meta.get("width"),
        "original_height": orig_meta.get("height"),
        "export_format": export_format,
        "quality": quality,
        "mode": mode,
        "bg_color_hex": bg_color_hex,
        "is_transparent": is_transparent,
        "sharpen": sharpen,
        "denoise": denoise,
        "generated_at": time.time(),
        "outputs": results,
    }

    manifest_path = os.path.join(gen_session_dir, "metadata.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

    return session_data


def regenerate_single_ratio(
    image_id: str,
    ratio_safe_key: str,
    source_image_path: Optional[str] = None,
    mode: Optional[str] = None,
    bg_color_hex: Optional[str] = None,
    is_transparent: Optional[bool] = None,
    manual_crop: Optional[Tuple[int, int, int, int]] = None
) -> Dict[str, Any]:
    """
    Regenerate a single ratio output without affecting the other four outputs.
    """
    _, gen_session_dir = get_image_session_dirs(image_id)
    manifest_path = os.path.join(gen_session_dir, "metadata.json")

    session_data = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)

    export_format = session_data.get("export_format", "jpeg")
    quality = session_data.get("quality", 90)
    proc_mode = mode or session_data.get("mode", "smart_crop")
    proc_bg_color = bg_color_hex or session_data.get("bg_color_hex", "#18181B")
    proc_transparent = is_transparent if is_transparent is not None else session_data.get("is_transparent", False)
    sharpen = session_data.get("sharpen", False)
    denoise = session_data.get("denoise", False)

    target_config = resolve_ratio_config(ratio_safe_key)
    if not target_config:
        raise ValueError(f"Invalid ratio identifier: {ratio_safe_key}")

    img_path = source_image_path or get_original_file_path(image_id)
    if not img_path or not os.path.exists(img_path):
        raise FileNotFoundError("Source image for ratio not found")

    ext = "jpg" if export_format == "jpeg" else export_format

    with Image.open(img_path) as source_img:
        source_img = fix_exif_orientation(source_img)
        source_img = ensure_srgb_profile(source_img)
        orig_w, orig_h = source_img.size

        processed, crop_box = process_image_for_ratio(
            img=source_img,
            target_config=target_config,
            mode=proc_mode,
            bg_color_hex=proc_bg_color,
            is_transparent=proc_transparent,
            manual_crop=manual_crop
        )

        if sharpen:
            processed = apply_mild_sharpening(processed)
        if denoise:
            processed = apply_mild_denoising(processed)

        if proc_transparent and export_format in ["png", "webp"]:
            final_img = processed.convert("RGBA")
        else:
            final_img = handle_alpha_transparency(
                processed,
                target_format=export_format,
                bg_color_hex=proc_bg_color
            )

        out_filename = f"image_{target_config['safe_key']}.{ext}"
        out_path = os.path.join(gen_session_dir, out_filename)

        save_kwargs = {}
        if export_format in ["jpeg", "webp"]:
            save_kwargs["quality"] = max(1, min(100, quality))
        if export_format == "png":
            save_kwargs["compress_level"] = 6
        final_img.save(out_path, format=export_format.upper(), **save_kwargs)

        legacy_path = os.path.join(gen_session_dir, f"image_{target_config['legacy_key']}.{ext}")
        if legacy_path != out_path:
            shutil.copyfile(out_path, legacy_path)

        thumb_scale = min(600 / target_config["width"], 600 / target_config["height"], 1.0)
        thumb_w = int(round(target_config["width"] * thumb_scale))
        thumb_h = int(round(target_config["height"] * thumb_scale))
        thumb_img = final_img.resize((thumb_w, thumb_h), resample=Image.Resampling.LANCZOS)

        thumb_filename = f"thumb_{target_config['safe_key']}.webp"
        thumb_path = os.path.join(gen_session_dir, thumb_filename)
        thumb_img.save(thumb_path, format="WEBP", quality=82)

        legacy_thumb_path = os.path.join(gen_session_dir, f"thumb_{target_config['legacy_key']}.webp")
        if legacy_thumb_path != thumb_path:
            shutil.copyfile(thumb_path, legacy_thumb_path)

        file_size = os.path.getsize(out_path)

        crop_w = crop_box[2] - crop_box[0]
        crop_h = crop_box[3] - crop_box[1]
        edges_trimmed = (crop_w < orig_w * 0.85) or (crop_h < orig_h * 0.85)

        output_entry = {
            "ratio_key": target_config["ratio_key"],
            "safe_key": target_config["safe_key"],
            "legacy_key": target_config["legacy_key"],
            "name": target_config["name"],
            "width": target_config["width"],
            "height": target_config["height"],
            "orientation": target_config["orientation"],
            "file_name": out_filename,
            "file_size": file_size,
            "file_path": out_path,
            "preview_url": f"/api/preview/{image_id}/{target_config['safe_key']}",
            "download_url": f"/api/download/{image_id}/{target_config['safe_key']}",
            "crop_box": list(crop_box),
            "mode": proc_mode,
            "edges_trimmed": edges_trimmed and proc_mode == "smart_crop",
        }

    # Update manifest
    outputs = session_data.get("outputs", [])
    updated = False
    for i, out in enumerate(outputs):
        if out["safe_key"] == target_config["safe_key"] or out.get("legacy_key") == target_config["legacy_key"]:
            outputs[i] = output_entry
            updated = True
            break
    if not updated:
        outputs.append(output_entry)
    session_data["outputs"] = outputs

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

    return output_entry
