"""Tests for Standard Resize vs AI Enhanced Resize comparison workflow."""

import io
import json
import zipfile
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from main import app
from services.ai_background_expander import (
    calculate_expansion_canvas,
    studio_texture_background_expansion,
    expand_background_product_safe,
)
from services.crop_engine import SIZE_PRESETS

client = TestClient(app)


def create_sample_image(format="JPEG", size=(1000, 800), color=(100, 150, 200)):
    buf = io.BytesIO()
    img = Image.new("RGB", size, color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def test_ai_canvas_builder_preserves_product_aspect_ratio():
    """Verify calculate_expansion_canvas does not stretch the source image."""
    # Source is 600x400 (aspect 1.5), target is 16:9 (2560x1440, aspect 1.777)
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(600, 400, 2560, 1440)

    # Placed product must maintain exact 1.5 aspect ratio
    assert ph == 1440
    assert abs(pw / float(ph) - 1.5) < 0.01
    assert ext_type == "horizontal"
    assert ox > 0  # Horizontal expansion margins
    assert oy == 0


def test_studio_texture_expansion_retains_source_pixels():
    """Verify studio_texture_background_expansion embeds pristine source pixels."""
    src = Image.new("RGB", (300, 200), (255, 0, 0)) # Pure red
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(300, 200, 400, 200)

    expanded = studio_texture_background_expansion(
        img_rgb=src,
        target_w=400,
        target_h=200,
        placed_w=pw,
        placed_h=ph,
        offset_x=ox,
        offset_y=oy,
        expansion_type=ext_type,
    )

    assert expanded.size == (400, 200)
    # Center pixel must be pure red from source
    r, g, b = expanded.getpixel((200, 100))
    assert r > 240 and g < 20 and b < 20


def test_convert_comparison_endpoint_generates_standard_and_ai_rows():
    """Verify POST /api/convert-comparison generates 5 comparison rows with exact specifications."""
    img_bytes = create_sample_image("JPEG", (1200, 900))
    upload_res = client.post("/api/upload", files={"file": ("product.jpg", img_bytes, "image/jpeg")})
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    res = client.post("/api/convert-comparison", json={
        "image_id": image_id,
        "export_format": "jpeg",
        "quality": 90,
    })
    assert res.status_code == 200
    data = res.json()

    assert data["image_id"] == image_id
    assert "ai_status" in data
    assert len(data["rows"]) == 5

    expected_safe_keys = ["square_1x1", "portrait_4x5", "portrait_3x4", "landscape_16x9", "landscape_5x4"]
    returned_keys = [r["safe_key"] for r in data["rows"]]
    assert returned_keys == expected_safe_keys

    for row in data["rows"]:
        safe_key = row["safe_key"]
        assert "standard" in row
        assert "ai" in row

        # Standard check
        std = row["standard"]
        assert std["method"] == "standard"
        assert std["status"] == "ready"
        assert len(std["variants"]) == 3

        expected_sizes = SIZE_PRESETS[safe_key]
        for v in std["variants"]:
            s_key = v["size_key"]
            assert (v["width"], v["height"]) == expected_sizes[s_key]
            assert v["selection_id"] == f"standard:{safe_key}:{s_key}"

        # AI check
        ai = row["ai"]
        assert ai["method"] == "ai"
        assert ai["status"] in ["ready", "unavailable", "fallback", "failed"]


def test_download_mixed_selection_zip():
    """Verify POST /api/download-selected packages mixed selections correctly."""
    img_bytes = create_sample_image("JPEG", (1200, 900))
    upload_res = client.post("/api/upload", files={"file": ("gadget.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]

    convert_res = client.post("/api/convert-comparison", json={
        "image_id": image_id,
        "export_format": "jpeg",
        "quality": 90,
    })
    assert convert_res.status_code == 200

    # Pick 3 standard variants across different ratios and sizes
    selections = [
        "standard:square_1x1:large",
        "standard:portrait_4x5:medium",
        "standard:landscape_16x9:small",
    ]

    zip_res = client.post("/api/download-selected", json={
        "image_id": image_id,
        "selections": selections,
    })
    assert zip_res.status_code == 200
    assert "application/zip" in zip_res.headers["content-type"]

    with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "standard_square_1x1_large.jpg" in namelist
        assert "standard_portrait_4x5_medium.jpg" in namelist
        assert "standard_landscape_16x9_small.jpg" in namelist
        assert len(namelist) == 4 # 3 images + 1 manifest

        # Check manifest content
        manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest_data["selected_count"] == 3
        assert len(manifest_data["files"]) == 3


def test_preview_and_download_routes_support_method():
    """Verify /api/preview and /api/download support method='standard' and size params."""
    img_bytes = create_sample_image("JPEG", (1000, 1000))
    upload_res = client.post("/api/upload", files={"file": ("item.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]

    client.post("/api/convert-comparison", json={"image_id": image_id})

    # Thumbnail preview with method
    prev_res = client.get(f"/api/preview/{image_id}/square_1x1?method=standard&size=medium")
    assert prev_res.status_code == 200
    assert "image/jpeg" in prev_res.headers["content-type"]

    # Full preview with method
    full_res = client.get(f"/api/preview-full/{image_id}/square_1x1?method=standard&size=large")
    assert full_res.status_code == 200

    # Download with method
    dl_res = client.get(f"/api/download/{image_id}/square_1x1?method=standard&size=large")
    assert dl_res.status_code == 200
    assert "standard_square_1x1_large.jpg" in dl_res.headers.get("content-disposition", "")
