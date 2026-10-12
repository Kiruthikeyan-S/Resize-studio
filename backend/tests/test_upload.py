"""Tests for upload validation and handling."""

import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def create_test_image_bytes(format="JPEG", size=(400, 300), color=(100, 150, 200)):
    buf = io.BytesIO()
    mode = "RGBA" if format == "PNG" else "RGB"
    img = Image.new(mode, size, color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def test_upload_valid_jpeg():
    img_bytes = create_test_image_bytes("JPEG", (600, 400))
    response = client.post(
        "/api/upload",
        files={"file": ("test_image.jpg", img_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "image_id" in data
    assert data["width"] == 600
    assert data["height"] == 400
    assert data["format"] == "JPEG"


def test_upload_valid_png():
    img_bytes = create_test_image_bytes("PNG", (500, 500))
    response = client.post(
        "/api/upload",
        files={"file": ("transparent.png", img_bytes, "image/png")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "PNG"
    assert data["width"] == 500
    assert data["height"] == 500


def test_upload_empty_file():
    response = client.post(
        "/api/upload",
        files={"file": ("empty.jpg", b"", "image/jpeg")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_corrupt_file():
    corrupt_bytes = b"NOT_AN_IMAGE_DATA_HEADER_CORRUPTED"
    response = client.post(
        "/api/upload",
        files={"file": ("bad.jpg", corrupt_bytes, "image/jpeg")}
    )
    assert response.status_code in [400, 422]
    assert "corrupted" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()


def test_path_traversal_sanitization():
    img_bytes = create_test_image_bytes("JPEG", (200, 200))
    response = client.post(
        "/api/upload",
        files={"file": ("../../../../etc/passwd.jpg", img_bytes, "image/jpeg")}
    )
    assert response.status_code == 200
    data = response.json()
    # The filename should be sanitized without traversal path
    assert ".." not in data["original_filename"]
    assert "/" not in data["original_filename"]
    assert "\\" not in data["original_filename"]


def test_upload_multiple_images():
    """Verify batch multi-image upload endpoint accepts multiple files simultaneously."""
    img1 = create_test_image_bytes("JPEG", (600, 400), color=(10, 20, 30))
    img2 = create_test_image_bytes("PNG", (400, 400), color=(50, 60, 70))
    img3 = create_test_image_bytes("JPEG", (800, 600), color=(100, 110, 120))

    files = [
        ("files", ("photo1.jpg", img1, "image/jpeg")),
        ("files", ("photo2.png", img2, "image/png")),
        ("files", ("photo3.jpg", img3, "image/jpeg")),
    ]

    response = client.post("/api/upload-multiple", files=files)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    assert data[0]["original_filename"] == "photo1.jpg"
    assert data[1]["original_filename"] == "photo2.png"
    assert data[2]["original_filename"] == "photo3.jpg"

    # Convert two of them and verify batch download
    id1 = data[0]["image_id"]
    id2 = data[1]["image_id"]
    client.post("/api/convert", json={"image_id": id1, "mode": "smart_crop"})
    client.post("/api/convert", json={"image_id": id2, "mode": "smart_crop"})

    batch_dl = client.get(f"/api/download-batch?image_ids={id1},{id2}")
    assert batch_dl.status_code == 200
    assert batch_dl.headers["content-type"] == "application/zip"
    assert len(batch_dl.content) > 1000

