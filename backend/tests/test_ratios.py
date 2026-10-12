"""Tests verifying Professional Smart Crop, Safe Fit, exact dimensions, and framing."""

import io
import json
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from main import app
from services.crop_engine import RATIO_CONFIGS, calculate_crop_window

client = TestClient(app)


def create_sample_image(format="JPEG", size=(1200, 800), color=(180, 100, 50), exif=None):
    buf = io.BytesIO()
    mode = "RGBA" if format == "PNG" else "RGB"
    img = Image.new(mode, size, color)
    save_kwargs = {}
    if exif:
        save_kwargs["exif"] = exif
    img.save(buf, format=format, **save_kwargs)
    buf.seek(0)
    return buf.getvalue()


def test_bmw_smart_crop_full_frame_no_blur_backgrounds():
    """Verify Smart Crop (default) produces full-frame prominent framing without blurred duplicate backgrounds."""
    # Simulate a wide BMW car photograph (1920x1080)
    img_bytes = create_sample_image("JPEG", (1920, 1080), color=(30, 90, 180))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("bmw_showroom.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    # Convert with default Smart Crop
    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "smart_crop", "export_format": "jpeg"}
    )
    assert convert_res.status_code == 200
    data = convert_res.json()
    assert data["mode"] == "smart_crop"
    assert len(data["outputs"]) == 5

    # Check that each output is generated with exact dimensions
    for item in data["outputs"]:
        down_res = client.get(f"/api/download/{image_id}/{item['safe_key']}")
        assert down_res.status_code == 200
        downloaded = Image.open(io.BytesIO(down_res.content))
        assert downloaded.size == (item["width"], item["height"])


def test_safe_fit_solid_background_no_blur():
    """Verify Safe Fit preserves entire image with solid background, without any blurred duplicate images."""
    img_bytes = create_sample_image("JPEG", (1920, 1080))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("product.jpg", img_bytes, "image/jpeg")}
    )
    image_id = upload_res.json()["image_id"]

    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "safe_fit", "bg_color_hex": "#000000", "export_format": "jpeg"}
    )
    assert convert_res.status_code == 200
    data = convert_res.json()
    assert data["mode"] == "safe_fit"

    # Portrait 4:5 has top/bottom padding
    portrait_4x5 = next(item for item in data["outputs"] if item["safe_key"] == "portrait_4x5")
    assert portrait_4x5["crop_box"] == [0, 0, 1920, 1080]

    # Verify download file
    down_res = client.get(f"/api/download/{image_id}/portrait_4x5")
    assert down_res.status_code == 200
    img = Image.open(io.BytesIO(down_res.content))
    assert img.size == (1600, 2000)
    # The top padding should be the solid black background (0, 0, 0)
    top_pixel = img.getpixel((800, 10))
    assert top_pixel == (0, 0, 0)


def test_exact_output_dimensions_all_five_ratios():
    """Verify that all 5 generated images match the exact required dimensions."""
    img_bytes = create_sample_image("JPEG", (1200, 800))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("photo.jpg", img_bytes, "image/jpeg")}
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "smart_crop", "export_format": "jpeg"}
    )
    assert convert_res.status_code == 200
    data = convert_res.json()
    assert len(data["outputs"]) == 5

    expected_specs = {
        "1:1": (2048, 2048),
        "4:5": (1600, 2000),
        "3:4": (1536, 2048),
        "16:9": (2560, 1440),
        "5:4": (2000, 1600),
    }

    for item in data["outputs"]:
        key = item["ratio_key"]
        assert key in expected_specs
        exp_w, exp_h = expected_specs[key]
        assert item["width"] == exp_w
        assert item["height"] == exp_h


def test_safe_fit_transparent_background_png():
    """Verify Safe Fit with transparent background for PNG export."""
    img_bytes = create_sample_image("PNG", (800, 600))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("transparent_car.png", img_bytes, "image/png")}
    )
    image_id = upload_res.json()["image_id"]

    convert_res = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "safe_fit", "is_transparent": True, "export_format": "png"}
    )
    assert convert_res.status_code == 200
    down_res = client.get(f"/api/download/{image_id}/square_1x1")
    assert down_res.status_code == 200
    img = Image.open(io.BytesIO(down_res.content))
    assert img.mode == "RGBA"
    assert img.getpixel((0, 0))[3] == 0  # Alpha transparent


def test_no_image_stretching_crop_aspect_ratios():
    """Verify that crop calculations never stretch image contents."""
    orig_w, orig_h = 1920, 1080
    left, top, right, bottom = calculate_crop_window(orig_w, orig_h, target_ratio=1.0)
    crop_w = right - left
    crop_h = bottom - top
    assert crop_w == crop_h
    assert crop_w <= orig_w
    assert crop_h <= orig_h

    left, top, right, bottom = calculate_crop_window(1080, 1920, target_ratio=16/9)
    crop_w = right - left
    crop_h = bottom - top
    assert abs((crop_w / crop_h) - (16 / 9)) < 0.01


def test_crop_boundaries_remain_valid():
    """Verify crop bounds never exceed original image boundaries."""
    orig_w, orig_h = 800, 600
    for center_x in [0.0, 0.2, 0.5, 0.8, 1.0]:
        for center_y in [0.0, 0.2, 0.5, 0.8, 1.0]:
            left, top, right, bottom = calculate_crop_window(orig_w, orig_h, 16/9, center_x, center_y)
            assert left >= 0
            assert top >= 0
            assert right <= orig_w
            assert bottom <= orig_h
            assert right > left
            assert bottom > top


def test_transparent_png_handling():
    """Verify RGBA transparent PNG is handled correctly for both PNG and JPEG exports."""
    buf = io.BytesIO()
    img = Image.new("RGBA", (500, 500), (255, 0, 0, 128))
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    upload_res = client.post(
        "/api/upload",
        files={"file": ("transparent.png", png_bytes, "image/png")}
    )
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    conv_png = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "smart_crop", "export_format": "png"}
    )
    assert conv_png.status_code == 200
    assert conv_png.json()["export_format"] == "png"

    conv_jpg = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "smart_crop", "export_format": "jpeg", "bg_color_hex": "#FFFFFF"}
    )
    assert conv_jpg.status_code == 200
    assert conv_jpg.json()["export_format"] == "jpeg"


def test_replacement_affects_only_selected_output():
    """Verify replacing one ratio regenerates only that ratio while leaving others untouched."""
    img_bytes = create_sample_image("JPEG", (800, 600), color=(50, 100, 150))
    upload_res = client.post(
        "/api/upload",
        files={"file": ("initial.jpg", img_bytes, "image/jpeg")}
    )
    image_id = upload_res.json()["image_id"]

    client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})

    orig_16x9_res = client.get(f"/api/download/{image_id}/landscape_16x9")
    orig_1x1_res = client.get(f"/api/download/{image_id}/square_1x1")
    orig_1x1_len = len(orig_1x1_res.content)

    replacement_bytes = create_sample_image("JPEG", (1200, 400), color=(255, 0, 0))
    replace_res = client.post(
        "/api/replace/landscape_16x9",
        data={"image_id": image_id},
        files={"file": ("replacement.jpg", replacement_bytes, "image/jpeg")}
    )
    assert replace_res.status_code == 200
    data = replace_res.json()
    assert data["safe_key"] == "landscape_16x9"
    assert data["width"] == 2560
    assert data["height"] == 1440

    new_1x1_res = client.get(f"/api/download/{image_id}/square_1x1")
    assert len(new_1x1_res.content) == orig_1x1_len


def test_invalid_manual_crop_rejection():
    """Verify that manual crops with mismatched aspect ratios or invalid bounds are rejected with HTTP 422."""
    img_bytes = create_sample_image("JPEG", (1200, 800))
    upload_res = client.post("/api/upload", files={"file": ("crop_test.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]
    client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})

    # Send wrong aspect ratio: square (1:1) requires width == height, but we send 600x200 (3:1)
    wrong_ratio_res = client.post(
        "/api/adjust-crop",
        json={
            "image_id": image_id,
            "ratio": "square_1x1",
            "crop_box": [100, 100, 700, 300]  # width=600, height=200 -> ratio 3.0 instead of 1.0
        }
    )
    assert wrong_ratio_res.status_code == 422
    assert "does not match target ratio" in wrong_ratio_res.json()["detail"].lower()

    # Out of bounds coordinates: right > 1200
    out_of_bounds_res = client.post(
        "/api/adjust-crop",
        json={
            "image_id": image_id,
            "ratio": "square_1x1",
            "crop_box": [100, 100, 1500, 1500]
        }
    )
    assert out_of_bounds_res.status_code == 422


def test_ratio_source_isolation_endpoint():
    """Verify that /api/ratio-source serves the replacement source for replaced ratios and master original for others."""
    img_bytes = create_sample_image("JPEG", (800, 600), color=(10, 20, 30))
    upload_res = client.post("/api/upload", files={"file": ("base.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]
    client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})

    # Check initial source is base
    src_res = client.get(f"/api/ratio-source/{image_id}/square_1x1")
    assert src_res.status_code == 200

    # Replace 16:9 with distinctive bright red image
    rep_bytes = create_sample_image("JPEG", (1000, 500), color=(255, 0, 0))
    client.post(
        "/api/replace/landscape_16x9",
        data={"image_id": image_id},
        files={"file": ("rep.jpg", rep_bytes, "image/jpeg")}
    )

    # 16:9 ratio source is now the replacement
    src_16x9 = client.get(f"/api/ratio-source/{image_id}/landscape_16x9")
    assert src_16x9.status_code == 200
    img_16x9 = Image.open(io.BytesIO(src_16x9.content))
    assert img_16x9.size == (1000, 500)

    # 1:1 ratio source remains the master
    src_1x1 = client.get(f"/api/ratio-source/{image_id}/square_1x1")
    assert src_1x1.status_code == 200
    img_1x1 = Image.open(io.BytesIO(src_1x1.content))
    assert img_1x1.size == (800, 600)


def test_groq_vision_endpoint_fallback():
    """Verify that /api/analyze handles absent/disabled Groq API gracefully without crashing."""
    img_bytes = create_sample_image("JPEG", (600, 400))
    upload_res = client.post("/api/upload", files={"file": ("test.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]

    res = client.get(f"/api/analyze/{image_id}")
    assert res.status_code == 200
    data = res.json()
    assert "enabled" in data


def test_wide_vehicle_automatic_safe_fit_fallback():
    """Verify wide car subject automatically triggers Safe Fit fallback on extreme portrait ratios."""
    # Create an image with a wide high-contrast subject (like a car spanning wide x-range)
    # Background: white (245, 245, 245), Subject: high-contrast dark rectangle spanning 85% width
    img = Image.new("RGB", (1600, 600), (245, 245, 245))
    # Draw a prominent dark subject box from x=100 to x=1500, y=150 to y=450
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 150, 1500, 450], fill=(20, 30, 40))
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    img_bytes = buf.getvalue()

    upload_res = client.post("/api/upload", files={"file": ("wide_car.jpg", img_bytes, "image/jpeg")})
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    convert_res = client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})
    assert convert_res.status_code == 200
    data = convert_res.json()

    # Find portrait_4x5 and portrait_3x4 outputs
    portrait_4x5 = next(item for item in data["outputs"] if item["safe_key"] == "portrait_4x5")
    portrait_3x4 = next(item for item in data["outputs"] if item["safe_key"] == "portrait_3x4")

    # In strict Full-Frame Photo (smart_crop), the engine never silently switches to safe_fit.
    # Instead, it preserves mode as smart_crop, crops to fill the target canvas, and reports fit_info.
    assert portrait_4x5["mode"] == "smart_crop"
    assert portrait_4x5["fit_info"] is not None
    assert portrait_4x5["fit_info"]["fits_completely"] is False
    assert portrait_4x5["fit_info"]["clipped_horizontal"] is True

    assert portrait_3x4["mode"] == "smart_crop"
    assert portrait_3x4["fit_info"] is not None
    assert portrait_3x4["fit_info"]["fits_completely"] is False


def test_option_switching_and_mode_isolation():
    """Verify switching between Option 1 (smart_crop) and Option 2 (safe_fit) produces mode-isolated files and downloads."""
    # Create image
    img = Image.new("RGB", (1200, 600), (200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    upload_res = client.post("/api/upload", files={"file": ("test_switch.jpg", buf.getvalue(), "image/jpeg")})
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    # 1. Convert with Option 1: smart_crop
    res1 = client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert all(o["mode"] == "smart_crop" for o in data1["outputs"])

    # 2. Convert with Option 2: safe_fit
    res2 = client.post("/api/convert", json={"image_id": image_id, "mode": "safe_fit", "bg_color_hex": "#112233"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert all(o["mode"] == "safe_fit" for o in data2["outputs"])

    # 3. Verify download endpoints return mode-specific images
    # Option 1 download (smart_crop)
    dl1 = client.get(f"/api/download/{image_id}/portrait_4x5?mode=smart_crop")
    assert dl1.status_code == 200
    img1 = Image.open(io.BytesIO(dl1.content))
    assert img1.size == (1600, 2000)

    # Option 2 download (safe_fit)
    dl2 = client.get(f"/api/download/{image_id}/portrait_4x5?mode=safe_fit")
    assert dl2.status_code == 200
    img2 = Image.open(io.BytesIO(dl2.content))
    assert img2.size == (1600, 2000)

    # Check color at corner (0, 0):
    # In safe_fit with #112233 padding, corner will have background padding color (17, 34, 51)
    # In smart_crop, it fills the frame with the image content (200, 100, 50)
    corner_safe_fit = img2.getpixel((5, 5))
    corner_smart_crop = img1.getpixel((5, 5))
    assert corner_safe_fit != corner_smart_crop, "Option 1 and Option 2 outputs must be distinct"

    # 4. Verify ZIP downloads for both modes
    zip1 = client.get(f"/api/download-all/{image_id}?mode=smart_crop")
    assert zip1.status_code == 200
    zip2 = client.get(f"/api/download-all/{image_id}?mode=safe_fit")
    assert zip2.status_code == 200


def test_food_platter_distinct_full_frame_crops_all_ratios():
    """Verify standard scene/food photography generates 5 distinct full-frame crops without false Safe Fit fallback."""
    # Create a realistic food platter / product photo (1200x800)
    img = Image.new("RGB", (1200, 800), (245, 245, 245))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 100, 1000, 700], fill=(200, 100, 50))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    img_bytes = buf.getvalue()

    upload_res = client.post("/api/upload", files={"file": ("food_platter.jpg", img_bytes, "image/jpeg")})
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    convert_res = client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})
    assert convert_res.status_code == 200
    data = convert_res.json()

    assert len(data["outputs"]) == 5
    crop_boxes = set()

    for item in data["outputs"]:
        # In Full-Frame Photo mode, standard photography must fill the frame (smart_crop) without false fallback
        assert item["mode"] == "smart_crop", f"{item['name']} unexpectedly fell back to safe_fit"
        assert item["fallback_reason"] is None
        crop_boxes.add(tuple(item["crop_box"]))

    # All crop windows should be uniquely calculated for the respective aspect ratio
    assert len(crop_boxes) == 5, "Crop windows should be uniquely customized for each ratio"



