"""Tests for CNN-based Super-Resolution, Protected Foreground Compositing,
File Immutability, Exact Dimensions, and Fallback Handling.
"""

import os
import io
import json
import hashlib
import pytest
from PIL import Image
import numpy as np
from fastapi.testclient import TestClient

from main import app
from services.crop_engine import SIZE_PRESETS, RATIO_CONFIGS
from services.super_resolution import (
    fallback_super_resolution,
    enhance_image_with_realesrgan,
    get_or_create_enhanced_master,
    is_torch_available,
)
from services.ai_background_expander import (
    composite_protected_foreground,
    calculate_expansion_canvas,
    expand_background_groq,
)
from services.image_processor import (
    get_image_session_dirs,
    get_original_file_path,
    get_raw_file_path,
    get_original_metadata,
)

client = TestClient(app)


def create_test_image(format="JPEG", size=(120, 90), color=(120, 180, 240)):
    """Helper to create test image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB" if format == "JPEG" else "RGBA", size, color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def get_file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# -------------------------------------------------------------------------
# 1. Exact Output Dimensions for All Ratios & Sizes
# -------------------------------------------------------------------------

def test_exact_output_dimensions_all_ratios_and_sizes():
    """Verify all 5 ratios and all 3 sizes (Large, Medium, Small) match exact dimensions."""
    img_bytes = create_test_image("JPEG", (120, 90))
    upload_res = client.post("/api/upload", files={"file": ("product_sr.jpg", img_bytes, "image/jpeg")})
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    # Convert with enhanced foreground choice
    conv_res = client.post("/api/convert-comparison", json={
        "image_id": image_id,
        "export_format": "jpeg",
        "quality": 90,
        "foreground_mode": "enhanced",
    })
    assert conv_res.status_code == 200
    data = conv_res.json()

    assert len(data["rows"]) == 5

    for row in data["rows"]:
        safe_key = row["safe_key"]
        expected_sizes = SIZE_PRESETS[safe_key]

        # Verify Standard (Method A) variants
        std = row["standard"]
        assert len(std["variants"]) == 3
        for v in std["variants"]:
            s_key = v["size_key"]
            assert (v["width"], v["height"]) == expected_sizes[s_key]

        # Verify AI (Method B) variants
        ai = row["ai"]
        assert len(ai["variants"]) == 3
        for v in ai["variants"]:
            s_key = v["size_key"]
            assert (v["width"], v["height"]) == expected_sizes[s_key]


# -------------------------------------------------------------------------
# 2. Original-File Immutability & Master Caching
# -------------------------------------------------------------------------

def test_original_file_immutability_and_caching():
    """Verify raw upload and approved working.png are immutable before and after super-resolution."""
    img_bytes = create_test_image("JPEG", (100, 80))
    upload_res = client.post("/api/upload", files={"file": ("master_item.jpg", img_bytes, "image/jpeg")})
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    orig_dir, _ = get_image_session_dirs(image_id)
    working_path = os.path.join(orig_dir, "working.png")
    raw_path = get_raw_file_path(image_id)

    assert os.path.exists(working_path)
    assert os.path.exists(raw_path)

    # Compute baseline SHA-256 hashes
    hash_raw_before = get_file_sha256(raw_path)
    hash_working_before = get_file_sha256(working_path)

    # Trigger super-resolution enhancement through convert-comparison
    conv_res = client.post("/api/convert-comparison", json={
        "image_id": image_id,
        "export_format": "jpeg",
        "quality": 90,
        "foreground_mode": "enhanced",
    })
    assert conv_res.status_code == 200

    # Verify hashes AFTER generation: working.png and raw MUST BE 100% BIT-FOR-BIT IDENTICAL
    hash_raw_after = get_file_sha256(raw_path)
    hash_working_after = get_file_sha256(working_path)

    assert hash_raw_before == hash_raw_after, "raw.* upload file was mutated!"
    assert hash_working_before == hash_working_after, "working.png source was mutated!"

    # Verify enhanced master was saved separately into cache
    cache_file = os.path.join(orig_dir, "enhanced_v1_RealESRGAN_x4plus_x4.png")
    assert os.path.exists(cache_file), f"Enhanced master was not cached at {cache_file}"

    # Verify enhanced master has 4x resolution
    with Image.open(cache_file) as enh_img:
        assert enh_img.size == (100 * 4, 80 * 4)


# -------------------------------------------------------------------------
# 3. Super-Resolution Fallback Handling
# -------------------------------------------------------------------------

def test_fallback_super_resolution():
    """Verify fallback_super_resolution operates correctly when neural model is bypassed."""
    img = Image.new("RGB", (100, 80), (200, 100, 50))
    res, meta = fallback_super_resolution(img, scale=2)

    assert res.size == (200, 160)
    assert meta["status"] == "fallback"
    assert meta["provider"] == "studio_fallback"
    assert meta["is_neural_sr"] is False
    assert meta["scale"] == 2


def test_ai_expansion_with_fallback_reporting():
    """Verify expand_background_groq reports studio_fallback honestly if AI is disabled."""
    img = Image.new("RGB", (150, 100), (80, 140, 200))
    res, meta = expand_background_groq(
        img=img,
        target_w=200,
        target_h=100,
        allow_opencv_fallback=True,
        foreground_mode="enhanced",
    )

    assert res.size == (200, 100)
    assert meta["status"] in ["ready", "fallback"]
    assert meta["foreground_mode"] == "enhanced"
    assert meta["foreground_fidelity"] == "ai_enhanced_detail"


# -------------------------------------------------------------------------
# 4. Transparent RGBA Images Handling
# -------------------------------------------------------------------------

def test_transparent_images_handling():
    """Verify RGBA images with transparency maintain alpha channel and composite without fringing."""
    rgba_img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(rgba_img)
    draw.ellipse([25, 25, 75, 75], fill=(255, 100, 50, 255))

    # Test super-resolution fallback with RGBA
    enhanced, meta = fallback_super_resolution(rgba_img, scale=2)
    assert enhanced.size == (200, 200)
    assert enhanced.mode == "RGBA"
    # Corner should remain transparent (alpha = 0)
    assert enhanced.getpixel((0, 0))[3] == 0
    # Center circle should be opaque (alpha = 255)
    assert enhanced.getpixel((100, 100))[3] == 255

    # Test composite_protected_foreground with RGBA
    bg = Image.new("RGB", (300, 200), (240, 240, 245))
    composited = composite_protected_foreground(
        background_img=bg,
        foreground_img=rgba_img,
        target_w=300,
        target_h=200,
        orig_w=100,
        orig_h=100,
    )

    assert composited.size == (300, 200)
    corner_rgb = composited.getpixel((10, 10))
    assert abs(corner_rgb[0] - 240) < 5


# -------------------------------------------------------------------------
# 5. Protected Foreground Compositing & Fidelity Choice
# -------------------------------------------------------------------------

def test_protected_compositing_geometry():
    """Verify composite_protected_foreground respects expansion geometry and borders."""
    bg = Image.new("RGB", (400, 300), (50, 50, 50))
    fg = Image.new("RGB", (200, 200), (255, 0, 0))

    comp = composite_protected_foreground(
        background_img=bg,
        foreground_img=fg,
        target_w=400,
        target_h=300,
        orig_w=200,
        orig_h=200,
    )

    assert comp.size == (400, 300)
    # Center pixel must be red
    center_rgb = comp.getpixel((200, 150))
    assert center_rgb[0] > 240 and center_rgb[1] < 15 and center_rgb[2] < 15

    # Left wing pixel outside placed foreground must be background tone
    left_rgb = comp.getpixel((10, 150))
    assert abs(left_rgb[0] - 50) < 10


def test_foreground_choice_fidelity_labeling():
    """Verify fidelity metadata differentiates original (pixel_identical) vs enhanced (ai_enhanced_detail)."""
    img_bytes = create_test_image("JPEG", (80, 60))
    upload_res = client.post("/api/upload", files={"file": ("choice_test.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]

    # 1. Test foreground_mode="original"
    res_orig = client.post("/api/convert-comparison", json={
        "image_id": image_id,
        "foreground_mode": "original",
    })
    data_orig = res_orig.json()
    assert data_orig["foreground_mode"] == "original"
    assert data_orig["foreground_fidelity"] == "pixel_identical"

    for r in data_orig["rows"]:
        ai = r["ai"]
        assert ai["foreground_mode"] == "original"
        assert ai["foreground_fidelity"] == "pixel_identical"
        assert "without alteration" in ai.get("foreground_description", "")

    # 2. Test foreground_mode="enhanced"
    res_enh = client.post("/api/convert-comparison", json={
        "image_id": image_id,
        "foreground_mode": "enhanced",
    })
    data_enh = res_enh.json()
    assert data_enh["foreground_mode"] == "enhanced"
    assert data_enh["foreground_fidelity"] == "ai_enhanced_detail"

    for r in data_enh["rows"]:
        ai = r["ai"]
        assert ai["foreground_mode"] == "enhanced"
        assert ai["foreground_fidelity"] == "ai_enhanced_detail"
        # Never claim enhanced copy is pixel-identical
        assert "Not claimed to be pixel-identical" in ai.get("foreground_description", "")
