"""Tests for manual crop coordinate handling, master cropping, and multi-ratio generation from cropped master."""

import io
from PIL import Image
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def create_gradient_test_image(width: int = 400, height: int = 300) -> bytes:
    """Create a synthetic RGB test image with distinct colors in corners."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    pixels = img.load()
    # Color top-left red, top-right green, bottom-left blue, bottom-right yellow
    for y in range(height):
        for x in range(width):
            if x < width // 2 and y < height // 2:
                pixels[x, y] = (255, 0, 0)
            elif x >= width // 2 and y < height // 2:
                pixels[x, y] = (0, 255, 0)
            elif x < width // 2 and y >= height // 2:
                pixels[x, y] = (0, 0, 255)
            else:
                pixels[x, y] = (255, 255, 0)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_manual_crop_updates_working_image_and_metadata():
    img_bytes = create_gradient_test_image(400, 300)
    files = {"file": ("test_frame.png", img_bytes, "image/png")}
    up_resp = client.post("/api/upload", files=files)
    assert up_resp.status_code == 200
    data = up_resp.json()
    image_id = data["image_id"]
    assert data["width"] == 400
    assert data["height"] == 300
    assert data["is_cropped_master"] is False

    # Apply manual crop: center 200x150 region [left: 100, top: 75, right: 300, bottom: 225]
    crop_payload = {
        "image_id": image_id,
        "crop_box": [100, 75, 300, 225],
    }
    update_resp = client.post("/api/update-original", json=crop_payload)
    assert update_resp.status_code == 200
    up_data = update_resp.json()
    assert up_data["width"] == 200
    assert up_data["height"] == 150
    assert up_data["raw_width"] == 400
    assert up_data["raw_height"] == 300
    assert up_data["is_cropped_master"] is True
    assert up_data["master_crop_box"] == [100, 75, 300, 225]

    # Verify working image stream is updated to 200x150
    working_resp = client.get(f"/api/original/{image_id}")
    assert working_resp.status_code == 200
    with Image.open(io.BytesIO(working_resp.content)) as work_img:
        assert work_img.size == (200, 150)

    # Convert after crop: all 5 ratios and all 15 variants must generate from the 200x150 working master
    conv_resp = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "smart_crop"},
    )
    assert conv_resp.status_code == 200
    conv_data = conv_resp.json()
    outputs = conv_data["outputs"]
    assert len(outputs) == 5

    for out in outputs:
        assert out["source_width"] == 200
        assert out["source_height"] == 150
        variants = out.get("variants", [])
        assert len(variants) == 3
        sizes = {v["size_key"]: (v["width"], v["height"]) for v in variants}
        assert "large" in sizes and "medium" in sizes and "small" in sizes

    # Revert to raw untouched original
    reset_resp = client.post(f"/api/reset-original/{image_id}")
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["width"] == 400
    assert reset_data["height"] == 300
    assert reset_data["is_cropped_master"] is False
    assert reset_data["master_crop_box"] is None


def test_manual_crop_clamping_and_validation():
    img_bytes = create_gradient_test_image(200, 200)
    files = {"file": ("clamp_test.png", img_bytes, "image/png")}
    up_resp = client.post("/api/upload", files=files)
    assert up_resp.status_code == 200
    image_id = up_resp.json()["image_id"]

    # Test out-of-bounds coordinates clamp safely
    crop_payload = {
        "image_id": image_id,
        "crop_box": [-50, -30, 500, 600],
    }
    update_resp = client.post("/api/update-original", json=crop_payload)
    assert update_resp.status_code == 200
    up_data = update_resp.json()
    assert up_data["width"] == 200
    assert up_data["height"] == 200

    # Test malformed crop box
    bad_payload = {
        "image_id": image_id,
        "crop_box": [10, 20],  # only 2 elements instead of 4
    }
    bad_resp = client.post("/api/update-original", json=bad_payload)
    assert bad_resp.status_code == 422


def test_download_specific_size_variant():
    img_bytes = create_gradient_test_image(300, 300)
    files = {"file": ("variant_dl_test.png", img_bytes, "image/png")}
    up_resp = client.post("/api/upload", files=files)
    assert up_resp.status_code == 200
    image_id = up_resp.json()["image_id"]

    conv_resp = client.post(
        "/api/convert",
        json={"image_id": image_id, "mode": "smart_crop"},
    )
    assert conv_resp.status_code == 200

    # Download medium variant for square_1x1 (should be 1024x1024)
    dl_med = client.get(f"/api/download/{image_id}/square_1x1?size=medium")
    assert dl_med.status_code == 200
    with Image.open(io.BytesIO(dl_med.content)) as im:
        assert im.size == (1024, 1024)

    # Download small variant for square_1x1 (should be 512x512)
    dl_small = client.get(f"/api/download/{image_id}/square_1x1?size=small")
    assert dl_small.status_code == 200
    with Image.open(io.BytesIO(dl_small.content)) as im:
        assert im.size == (512, 512)

    # Download large variant for square_1x1 (should be 2048x2048)
    dl_large = client.get(f"/api/download/{image_id}/square_1x1?size=large")
    assert dl_large.status_code == 200
    with Image.open(io.BytesIO(dl_large.content)) as im:
        assert im.size == (2048, 2048)

