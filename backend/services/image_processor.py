"""Image processor pipeline integrating validation, subject framing, lossless upload caching, and quality management."""

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
    detect_saliency_bbox,
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
    Save uploaded original file completely untouched (no lossy re-encoding).
    Creates a normalized lossless working copy (PNG/RGB) with EXIF orientation corrected
    so that all subsequent ratio crops export directly from master quality without degradation.
    """
    orig_session_dir, _ = get_image_session_dirs(image_id)
    os.makedirs(orig_session_dir, exist_ok=True)

    # 1. Save uploaded file bit-for-bit unchanged
    raw_path = os.path.join(orig_session_dir, f"raw{extension}")
    with open(raw_path, "wb") as f:
        f.write(file_bytes)

    # 2. Inspect with Pillow and generate normalized working copy
    working_path = os.path.join(orig_session_dir, "working.png")
    with Image.open(raw_path) as img:
        img_fixed = fix_exif_orientation(img)
        img_fixed = ensure_srgb_profile(img_fixed)
        width, height = img_fixed.size
        mode = img_fixed.mode
        format_name = (img.format or extension.lstrip(".")).upper()
        # Save working copy as lossless PNG
        img_fixed.save(working_path, format="PNG")

    meta = {
        "image_id": image_id,
        "original_filename": original_filename,
        "width": width,
        "height": height,
        "file_size": len(file_bytes),
        "format": format_name,
        "mode": mode,
        "file_path": working_path,
        "raw_path": raw_path,
        "version": 1,
        "created_at": time.time(),
        "is_low_res": width < 1600 or height < 1200,
    }

    meta_path = os.path.join(orig_session_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return working_path, meta


def get_original_metadata(image_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve original image metadata."""
    orig_session_dir, _ = get_image_session_dirs(image_id)
    meta_path = os.path.join(orig_session_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def get_raw_file_path(image_id: str) -> Optional[str]:
    """Retrieve untouched uploaded raw file path."""
    meta = get_original_metadata(image_id)
    if meta and "raw_path" in meta and os.path.exists(meta["raw_path"]):
        return meta["raw_path"]
    orig_session_dir, _ = get_image_session_dirs(image_id)
    for f in os.listdir(orig_session_dir):
        if f.startswith("raw."):
            return os.path.join(orig_session_dir, f)
    return None


def get_original_file_path(image_id: str) -> Optional[str]:
    """Retrieve working master image file path."""
    meta = get_original_metadata(image_id)
    if meta and "file_path" in meta and os.path.exists(meta["file_path"]):
        return meta["file_path"]
    orig_session_dir, _ = get_image_session_dirs(image_id)
    for candidate in ["working.png", "original.jpg", "original.png", "original.webp"]:
        p = os.path.join(orig_session_dir, candidate)
        if os.path.exists(p):
            return p
    return None


def update_working_image(
    image_id: str,
    crop_box: Tuple[int, int, int, int]
) -> Dict[str, Any]:
    """
    Apply user-adjusted framing (pan/zoom crop box) to create the new finalized working copy.
    The untouched original (raw) is preserved so the user can reset anytime.
    Updates working.png and increments version for cache busting.
    """
    orig_session_dir, _ = get_image_session_dirs(image_id)
    raw_path = get_raw_file_path(image_id)
    if not raw_path or not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw original file not found for session {image_id}")

    meta = get_original_metadata(image_id) or {}
    working_path = os.path.join(orig_session_dir, "working.png")

    with Image.open(raw_path) as img:
        img_fixed = fix_exif_orientation(img)
        img_fixed = ensure_srgb_profile(img_fixed)
        orig_w, orig_h = img_fixed.size

        left, top, right, bottom = crop_box
        # Bound coordinates to original image
        left = max(0, min(orig_w - 1, left))
        top = max(0, min(orig_h - 1, top))
        right = max(left + 10, min(orig_w, right))
        bottom = max(top + 10, min(orig_h, bottom))

        cropped = img_fixed.crop((left, top, right, bottom))
        # Save as new working master copy in lossless PNG
        cropped.save(working_path, format="PNG")

        new_w, new_h = cropped.size
        version = int(meta.get("version", 1)) + 1

        meta.update({
            "width": new_w,
            "height": new_h,
            "version": version,
            "is_cropped_master": True,
            "master_crop_box": [left, top, right, bottom],
            "raw_width": orig_w,
            "raw_height": orig_h,
        })

    meta_path = os.path.join(orig_session_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def reset_working_image(image_id: str) -> Dict[str, Any]:
    """
    Reset the working image back to the untouched raw upload.
    """
    orig_session_dir, _ = get_image_session_dirs(image_id)
    raw_path = get_raw_file_path(image_id)
    if not raw_path or not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw original file not found for session {image_id}")

    meta = get_original_metadata(image_id) or {}
    working_path = os.path.join(orig_session_dir, "working.png")

    with Image.open(raw_path) as img:
        img_fixed = fix_exif_orientation(img)
        img_fixed = ensure_srgb_profile(img_fixed)
        width, height = img_fixed.size
        img_fixed.save(working_path, format="PNG")

        version = int(meta.get("version", 1)) + 1
        meta.update({
            "width": width,
            "height": height,
            "version": version,
            "is_cropped_master": False,
            "master_crop_box": None,
        })

    meta_path = os.path.join(orig_session_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def get_ratio_source_info(image_id: str, ratio_safe_key: str) -> Tuple[str, str, int, int]:
    """
    Retrieve active source file path, source preview URL, and dimensions for a specific ratio.
    If an individual replacement was uploaded, returns the replacement source.
    Otherwise returns the session master source.
    Returns: (source_path, source_url, source_width, source_height)
    """
    orig_meta = get_original_metadata(image_id) or {}
    master_path = get_original_file_path(image_id) or ""
    master_w = orig_meta.get("width", 1920)
    master_h = orig_meta.get("height", 1080)

    # Check manifest for ratio-specific source override
    _, gen_session_dir = get_image_session_dirs(image_id)
    manifest_path = os.path.join(gen_session_dir, "metadata.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            for out in manifest.get("outputs", []):
                if out.get("safe_key") == ratio_safe_key:
                    rep_path = out.get("source_image_path")
                    if rep_path and os.path.exists(rep_path):
                        with Image.open(rep_path) as r_img:
                            rw, rh = r_img.size
                        rep_url = f"/api/ratio-source/{image_id}/{ratio_safe_key}"
                        return rep_path, rep_url, rw, rh
        except Exception:
            pass

    return master_path, f"/api/original/{image_id}", master_w, master_h


def generate_all_ratios(
    image_id: str,
    mode: str = "smart_crop",
    export_format: str = "jpeg",
    quality: int = 90,
    bg_color_hex: str = "#F8FAFC",
    is_transparent: bool = False,
    sharpen: bool = False,
    denoise: bool = False,
    custom_crops: Optional[Dict[str, Tuple[int, int, int, int]]] = None
) -> Dict[str, Any]:
    """
    Generate all 5 predefined aspect ratio images from master working copy.
    """
    orig_path = get_original_file_path(image_id)
    if not orig_path:
        raise FileNotFoundError(f"Original image not found for session {image_id}")

    orig_meta = get_original_metadata(image_id) or {}
    orig_version = orig_meta.get("version", 1)
    _, gen_session_dir = get_image_session_dirs(image_id)
    os.makedirs(gen_session_dir, exist_ok=True)

    export_format = export_format.lower()
    if export_format not in ["jpeg", "png", "webp"]:
        export_format = "jpeg"
    ext = "jpg" if export_format == "jpeg" else export_format

    custom_crops = custom_crops or {}

    manifest_path = os.path.join(gen_session_dir, "metadata.json")
    prev_manifest: Dict[str, Any] = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                prev_manifest = json.load(f)
        except Exception:
            pass

    revision = int(prev_manifest.get("revision", 0)) + 1

    results = []
    with Image.open(orig_path) as source_img:
        source_img = ensure_srgb_profile(source_img)
        orig_w, orig_h = source_img.size

        for ratio_key, config in RATIO_CONFIGS.items():
            safe_key = config["safe_key"]
            legacy_key = config["legacy_key"]
            manual_crop = custom_crops.get(ratio_key) or custom_crops.get(safe_key) or custom_crops.get(legacy_key)

            processed, crop_box, fit_info, effective_mode, fallback_reason = process_image_for_ratio(
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

            # Save mode-specific file to prevent cross-mode cache collisions
            mode_filename = f"image_{safe_key}_{effective_mode}.{ext}"
            mode_path = os.path.join(gen_session_dir, mode_filename)

            # Save full resolution output with high quality
            save_kwargs = {}
            if export_format == "jpeg":
                save_kwargs["quality"] = max(1, min(100, quality))
                save_kwargs["subsampling"] = 0  # 4:4:4 full chroma preservation
            elif export_format == "webp":
                save_kwargs["quality"] = max(1, min(100, quality))
                save_kwargs["method"] = 6
            elif export_format == "png":
                save_kwargs["compress_level"] = 6

            final_img.save(mode_path, format=export_format.upper(), **save_kwargs)

            # Also maintain canonical file name for backward compatibility
            out_filename = f"image_{safe_key}.{ext}"
            out_path = os.path.join(gen_session_dir, out_filename)
            if out_path != mode_path:
                shutil.copyfile(mode_path, out_path)

            # Legacy alias copy (e.g. image_1x1.jpg)
            legacy_filename = f"image_{legacy_key}.{ext}"
            legacy_path = os.path.join(gen_session_dir, legacy_filename)
            if legacy_path != out_path:
                shutil.copyfile(out_path, legacy_path)

            # High-fidelity preview thumbnail (max 640px)
            thumb_scale = min(640 / config["width"], 640 / config["height"], 1.0)
            thumb_w = int(round(config["width"] * thumb_scale))
            thumb_h = int(round(config["height"] * thumb_scale))
            thumb_img = final_img.resize((thumb_w, thumb_h), resample=Image.Resampling.LANCZOS)

            mode_thumb_filename = f"thumb_{safe_key}_{effective_mode}.webp"
            mode_thumb_path = os.path.join(gen_session_dir, mode_thumb_filename)
            thumb_img.save(mode_thumb_path, format="WEBP", quality=88)

            thumb_filename = f"thumb_{safe_key}.webp"
            thumb_path = os.path.join(gen_session_dir, thumb_filename)
            if thumb_path != mode_thumb_path:
                shutil.copyfile(mode_thumb_path, thumb_path)

            legacy_thumb_path = os.path.join(gen_session_dir, f"thumb_{legacy_key}.webp")
            if legacy_thumb_path != thumb_path:
                shutil.copyfile(thumb_path, legacy_thumb_path)

            file_size = os.path.getsize(mode_path)

            # Determine whether edge content was trimmed
            crop_w = crop_box[2] - crop_box[0]
            crop_h = crop_box[3] - crop_box[1]
            edges_trimmed = (crop_w < orig_w * 0.90) or (crop_h < orig_h * 0.90)

            version = revision
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
                "file_path": mode_path,
                "version": version,
                "preview_url": f"/api/preview/{image_id}/{safe_key}?mode={effective_mode}&v={version}",
                "download_url": f"/api/download/{image_id}/{safe_key}?mode={effective_mode}",
                "source_url": f"/api/original/{image_id}",
                "source_width": orig_w,
                "source_height": orig_h,
                "source_image_path": orig_path,
                "crop_box": list(crop_box),
                "mode": effective_mode,
                "edges_trimmed": edges_trimmed and effective_mode == "smart_crop",
                "fit_info": fit_info,
                "fallback_reason": fallback_reason,
            })

    outputs_by_mode = prev_manifest.get("outputs_by_mode", {})
    outputs_by_mode[mode] = results

    session_data = {
        "image_id": image_id,
        "original_filename": orig_meta.get("original_filename", "image"),
        "original_width": orig_meta.get("width"),
        "original_height": orig_meta.get("height"),
        "export_format": export_format,
        "quality": quality,
        "mode": mode,
        "revision": revision,
        "bg_color_hex": bg_color_hex,
        "is_transparent": is_transparent,
        "sharpen": sharpen,
        "denoise": denoise,
        "generated_at": time.time(),
        "outputs": results,
        "outputs_by_mode": outputs_by_mode,
    }

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
    Increments ratio version for stable preview cache invalidation.
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
    proc_bg_color = bg_color_hex or session_data.get("bg_color_hex", "#F8FAFC")
    proc_transparent = is_transparent if is_transparent is not None else session_data.get("is_transparent", False)
    sharpen = session_data.get("sharpen", False)
    denoise = session_data.get("denoise", False)

    target_config = resolve_ratio_config(ratio_safe_key)
    if not target_config:
        raise ValueError(f"Invalid ratio identifier: {ratio_safe_key}")

    # Find existing entry for this ratio to retain or update its specific source
    existing_entry = None
    for out in session_data.get("outputs", []):
        if out.get("safe_key") == target_config["safe_key"] or out.get("legacy_key") == target_config["legacy_key"]:
            existing_entry = out
            break

    # Determine source path
    if source_image_path:
        img_path = source_image_path
        is_custom_source = True
    elif existing_entry and existing_entry.get("source_image_path") and os.path.exists(existing_entry["source_image_path"]):
        img_path = existing_entry["source_image_path"]
        is_custom_source = img_path != get_original_file_path(image_id)
    else:
        img_path = get_original_file_path(image_id)
        is_custom_source = False

    if not img_path or not os.path.exists(img_path):
        raise FileNotFoundError("Source image for ratio not found")

    ext = "jpg" if export_format == "jpeg" else export_format
    current_version = (existing_entry.get("version", 1) if existing_entry else 1) + 1

    with Image.open(img_path) as source_img:
        source_img = fix_exif_orientation(source_img)
        source_img = ensure_srgb_profile(source_img)
        orig_w, orig_h = source_img.size

        processed, crop_box, fit_info, effective_mode, fallback_reason = process_image_for_ratio(
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

        mode_filename = f"image_{target_config['safe_key']}_{effective_mode}.{ext}"
        mode_path = os.path.join(gen_session_dir, mode_filename)

        save_kwargs = {}
        if export_format == "jpeg":
            save_kwargs["quality"] = max(1, min(100, quality))
            save_kwargs["subsampling"] = 0
        elif export_format == "webp":
            save_kwargs["quality"] = max(1, min(100, quality))
            save_kwargs["method"] = 6
        elif export_format == "png":
            save_kwargs["compress_level"] = 6

        final_img.save(mode_path, format=export_format.upper(), **save_kwargs)

        out_filename = f"image_{target_config['safe_key']}.{ext}"
        out_path = os.path.join(gen_session_dir, out_filename)
        if out_path != mode_path:
            shutil.copyfile(mode_path, out_path)

        legacy_path = os.path.join(gen_session_dir, f"image_{target_config['legacy_key']}.{ext}")
        if legacy_path != out_path:
            shutil.copyfile(out_path, legacy_path)

        thumb_scale = min(640 / target_config["width"], 640 / target_config["height"], 1.0)
        thumb_w = int(round(target_config["width"] * thumb_scale))
        thumb_h = int(round(target_config["height"] * thumb_scale))
        thumb_img = final_img.resize((thumb_w, thumb_h), resample=Image.Resampling.LANCZOS)

        mode_thumb_filename = f"thumb_{target_config['safe_key']}_{effective_mode}.webp"
        mode_thumb_path = os.path.join(gen_session_dir, mode_thumb_filename)
        thumb_img.save(mode_thumb_path, format="WEBP", quality=88)

        thumb_filename = f"thumb_{target_config['safe_key']}.webp"
        thumb_path = os.path.join(gen_session_dir, thumb_filename)
        if thumb_path != mode_thumb_path:
            shutil.copyfile(mode_thumb_path, thumb_path)

        legacy_thumb_path = os.path.join(gen_session_dir, f"thumb_{target_config['legacy_key']}.webp")
        if legacy_thumb_path != thumb_path:
            shutil.copyfile(thumb_path, legacy_thumb_path)

        file_size = os.path.getsize(mode_path)

        crop_w = crop_box[2] - crop_box[0]
        crop_h = crop_box[3] - crop_box[1]
        edges_trimmed = (crop_w < orig_w * 0.90) or (crop_h < orig_h * 0.90)

        source_url = (
            f"/api/ratio-source/{image_id}/{target_config['safe_key']}?v={current_version}"
            if is_custom_source
            else f"/api/original/{image_id}"
        )

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
            "file_path": mode_path,
            "version": current_version,
            "preview_url": f"/api/preview/{image_id}/{target_config['safe_key']}?mode={effective_mode}&v={current_version}",
            "download_url": f"/api/download/{image_id}/{target_config['safe_key']}?mode={effective_mode}",
            "source_url": source_url,
            "source_width": orig_w,
            "source_height": orig_h,
            "source_image_path": img_path,
            "crop_box": list(crop_box),
            "mode": effective_mode,
            "edges_trimmed": edges_trimmed and effective_mode == "smart_crop",
            "fit_info": fit_info,
            "fallback_reason": fallback_reason,
        }

    # Update manifest atomically
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
