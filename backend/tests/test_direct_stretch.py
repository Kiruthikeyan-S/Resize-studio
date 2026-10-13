"""Tests verifying Direct Stretch resizing, 15 fixed outputs, and workflow decoupling."""

import io
import json
import zipfile
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from main import app
from services.crop_engine import direct_stretch, RATIO_CONFIGS
from services.image_processor import SIZE_PRESETS, SIZE_KEYS

client = TestClient(app)


def create_gradient_image(size=(1200, 800), format="JPEG"):
    """Creates a distinct patterned image so pixel preservation can be verified."""
    img = Image.new("RGB", size)
    pixels = img.load()
    w, h = size
    for x in range(w):
        for y in range(h):
            r = int((x / max(w - 1, 1)) * 255)
            g = int((y / max(h - 1, 1)) * 255)
            b = 128
            pixels[x, y] = (r, g, b)
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def test_direct_stretch_unit_function():
    """Verify direct_stretch preserves all pixels and resizes directly without crop or pad."""
    src = Image.new("RGB", (1920, 1080), (100, 150, 200))
    # 16:9 -> 1:1
    stretched = direct_stretch(src, 2048, 2048)
    assert stretched.size == (2048, 2048)
    # Check that four corners and center retain source tone without borders/padding
    corners = [
        stretched.getpixel((0, 0)),
        stretched.getpixel((2047, 0)),
        stretched.getpixel((0, 2047)),
        stretched.getpixel((2047, 2047)),
        stretched.getpixel((1024, 1024)),
    ]
    for c in corners:
        assert c == (100, 150, 200)


@pytest.mark.parametrize(
    "src_w,src_h,ratio_key,target_w,target_h",
    [
        (1920, 1080, "square_1x1", 2048, 2048),     # 16:9 -> 1:1
        (1000, 1000, "landscape_16x9", 2560, 1440), # 1:1 -> 16:9
        (1200, 1500, "landscape_5x4", 2000, 1600),  # 4:5 -> 5:4
        (900, 1200, "landscape_16x9", 2560, 1440),  # 3:4 -> 16:9
        (1500, 1200, "portrait_4x5", 1600, 2000),   # 5:4 -> 4:5
    ]
)
def test_direct_stretch_aspect_ratio_pairs(src_w, src_h, ratio_key, target_w, target_h):
    """Test required aspect ratio conversions with direct stretch."""
    img_bytes = create_gradient_image((src_w, src_h))
    upload_res = client.post(
        "/api/upload",
        files={"file": (f"test_{src_w}x{src_h}.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "direct_stretch"}
    )
    assert convert_res.status_code == 200
    data = convert_res.json()
    assert data["mode"] == "direct_stretch"

    matched = next((o for o in data["outputs"] if o["safe_key"] == ratio_key), None)
    assert matched is not None
    assert matched["width"] == target_w
    assert matched["height"] == target_h

    # Check downloaded image size
    down_res = client.get(f"/api/download/{image_id}/{ratio_key}?mode=direct_stretch")
    assert down_res.status_code == 200
    out_img = Image.open(io.BytesIO(down_res.content))
    assert out_img.size == (target_w, target_h)


def test_all_15_fixed_output_resolutions():
    """Verify all 15 fixed outputs (5 ratios x 3 size presets: Large, Medium, Small) match exact dimensions."""
    img_bytes = create_gradient_image((1600, 1200))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("master.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "direct_stretch"}
    )
    assert convert_res.status_code == 200
    data = convert_res.json()

    # Expected exact sizes:
    expected_sizes = {
        "square_1x1": {"large": (2048, 2048), "medium": (1080, 1080), "small": (512, 512)},
        "portrait_4x5": {"large": (1600, 2000), "medium": (1080, 1350), "small": (800, 1000)},
        "portrait_3x4": {"large": (1536, 2048), "medium": (1080, 1440), "small": (768, 1024)},
        "landscape_16x9": {"large": (2560, 1440), "medium": (1920, 1080), "small": (1280, 720)},
        "landscape_5x4": {"large": (2000, 1600), "medium": (1350, 1080), "small": (1000, 800)},
    }

    assert len(data["outputs"]) == 5

    total_variants_verified = 0
    for out in data["outputs"]:
        safe_key = out["safe_key"]
        assert safe_key in expected_sizes
        assert len(out["variants"]) == 3

        for v in out["variants"]:
            s_key = v["size_key"]
            expected_dim = expected_sizes[safe_key][s_key]
            assert (v["width"], v["height"]) == expected_dim

            # Verify download of this variant
            down_res = client.get(f"/api/download/{image_id}/{safe_key}?size={s_key}")
            assert down_res.status_code == 200
            downloaded = Image.open(io.BytesIO(down_res.content))
            assert downloaded.size == expected_dim

            # Verify preview endpoint with size query parameter
            preview_res = client.get(f"/api/preview/{image_id}/{safe_key}?size={s_key}")
            assert preview_res.status_code == 200
            preview_img = Image.open(io.BytesIO(preview_res.content))
            assert preview_img.size == expected_dim

            total_variants_verified += 1

    assert total_variants_verified == 15


def test_workflow_done_does_not_generate_outputs_only_resize():
    """Verify Done (update-original) only saves cropped master, while Resize (/api/convert) generates outputs."""
    img_bytes = create_gradient_image((2000, 1500))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("sample_workflow.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    # 1. Customer performs crop and clicks Done (POST /api/update-original)
    crop_res = client.post(
        "/api/update-original",
        json={"image_id": image_id, "crop_box": [100, 100, 1600, 1100]}
    )
    assert crop_res.status_code == 200
    crop_data = crop_res.json()
    assert crop_data["is_cropped_master"] is True
    assert crop_data["width"] == 1500
    assert crop_data["height"] == 1000

    # Verify no generated outputs exist yet for this session
    preview_res = client.get(f"/api/preview/{image_id}/square_1x1")
    assert preview_res.status_code == 404

    # 2. Customer clicks Resize (POST /api/convert)
    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "direct_stretch"}
    )
    assert convert_res.status_code == 200
    out_data = convert_res.json()
    assert len(out_data["outputs"]) == 5

    # Now previews and downloads succeed
    preview_res2 = client.get(f"/api/preview/{image_id}/square_1x1")
    assert preview_res2.status_code == 200


def test_selected_zip_contains_only_selected_variants():
    """Verify ZIP contains only the selected variants from latest generation."""
    img_bytes = create_gradient_image((1400, 1000))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("zip_test.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "direct_stretch"}
    )
    assert convert_res.status_code == 200
    data = convert_res.json()
    revision = data.get("revision")

    # Select 3 specific variants: square_1x1:large, landscape_16x9:medium, portrait_4x5:small
    selections = ["square_1x1:large", "landscape_16x9:medium", "portrait_4x5:small"]
    zip_res = client.post(
        "/api/download-selected",
        json={"image_id": image_id, "selections": selections, "revision": revision}
    )
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        namelist = zf.namelist()
        image_files = [n for n in namelist if not n.endswith(".json")]
        assert len(image_files) == 3
        # Ensure filenames match selections
        assert any("square_1x1_large" in name for name in image_files)
        assert any("landscape_16x9_medium" in name for name in image_files)
        assert any("portrait_4x5_small" in name for name in image_files)
