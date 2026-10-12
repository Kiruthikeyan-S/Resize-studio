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
