"""Tests for download endpoints, ZIP generation with manifest, and session cleanup."""

import io
import json
import zipfile
from PIL import Image
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def create_sample_image(format="JPEG", size=(900, 600)):
    buf = io.BytesIO()
    img = Image.new("RGB", size, (70, 120, 190))
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def test_download_single_image_and_headers():
    img_bytes = create_sample_image("JPEG")
    upload_res = client.post("/api/upload", files={"file": ("photo.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]

    client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop", "export_format": "jpeg"})

    # Test downloading via descriptive safe key
    res = client.get(f"/api/download/{image_id}/square_1x1")
    assert res.status_code == 200
    assert "image/jpeg" in res.headers["content-type"]
    assert 'filename="image_square_1x1.jpg"' in res.headers["content-disposition"]

    # Test downloading via legacy key
    res_legacy = client.get(f"/api/download/{image_id}/1x1")
    assert res_legacy.status_code == 200

    img = Image.open(io.BytesIO(res.content))
    assert img.size == (2048, 2048)


def test_download_all_zip_archive_and_manifest():
    img_bytes = create_sample_image("JPEG")
    upload_res = client.post("/api/upload", files={"file": ("scenery.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]

    client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop", "export_format": "webp"})

    res = client.get(f"/api/download-all/{image_id}")
    assert res.status_code == 200
    assert "application/zip" in res.headers["content-type"]
    assert 'filename="ratio-studio-images.zip"' in res.headers["content-disposition"]

    # Verify ZIP contents
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        # Exactly 5 images + manifest.json
        assert len(namelist) == 6

        # Check manifest contents
        manifest_raw = zf.read("manifest.json").decode("utf-8")
        manifest = json.loads(manifest_raw)
        assert manifest["application"] == "Ratio Studio"
        assert manifest["processing_mode"] == "smart_crop"
        assert len(manifest["files"]) == 5


def test_delete_session():
    img_bytes = create_sample_image("JPEG")
    upload_res = client.post("/api/upload", files={"file": ("temp.jpg", img_bytes, "image/jpeg")})
    image_id = upload_res.json()["image_id"]

    client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})

    del_res = client.delete(f"/api/images/{image_id}")
    assert del_res.status_code == 200

    down_res = client.get(f"/api/download/{image_id}/square_1x1")
    assert down_res.status_code == 404
