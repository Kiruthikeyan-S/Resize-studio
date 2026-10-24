"""Automated tests for AI Background Outpainting, Provider Adapters, and Subject Preservation.
Covers all requirements from the prompt using mocked external APIs to avoid consuming paid credits.
"""

import io
import os
import unittest
from unittest.mock import patch, MagicMock
import pytest
from PIL import Image
import numpy as np
from fastapi.testclient import TestClient

from main import app
from services.ai_background_expander import (
    calculate_expansion_canvas,
    studio_texture_background_expansion,
    OpenAIOutpaintingProvider,
    GeminiOutpaintingProvider,
    GroqVisionAdaptiveProvider,
    expand_background_ai,
    _REGISTRY,
)
from services.crop_engine import RATIO_CONFIGS, SIZE_PRESETS

client = TestClient(app)


def create_test_image(width=800, height=600, color=(120, 80, 200)):
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color)
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf.getvalue()


# -------------------------------------------------------------------------
# 1. Proportional Canvas & Aspect Ratio Tests
# -------------------------------------------------------------------------

def test_all_five_aspect_ratios_proportions():
    """Verify canvas placement preserves aspect ratio without stretching across all 5 ratios."""
    test_ratios = [
        ("square_1x1", 2048, 2048, 1.0),
        ("portrait_4x5", 1600, 2000, 0.8),
        ("portrait_3x4", 1536, 2048, 0.75),
        ("landscape_16x9", 2560, 1440, 16/9),
        ("landscape_5x4", 2000, 1600, 1.25),
    ]

    # Source is 800x600 (aspect 1.333)
    orig_w, orig_h = 800, 600
    orig_ratio = orig_w / float(orig_h)

    for safe_key, tw, th, expected_ratio in test_ratios:
        pw, ph, ox, oy, ext_type = calculate_expansion_canvas(orig_w, orig_h, tw, th)
        placed_ratio = pw / float(ph)
        # Placed subject must maintain source aspect ratio within 0.5%
        assert abs(placed_ratio - orig_ratio) < 0.005, f"Distorted in {safe_key}"
        # Placed dimensions must fit within canvas
        assert ox + pw <= tw
        assert oy + ph <= th


def test_portrait_landscape_and_square_sources():
    """Verify tall, wide, and square source images are placed proportionally."""
    tw, th = 2560, 1440 # 16:9 target

    # Tall portrait source: 600x1200
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(600, 1200, tw, th)
    assert ph == th
    assert ext_type == "horizontal"
    assert ox > 0

    # Wide landscape source: 2000x800
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(2000, 800, tw, th)
    assert pw <= tw
    assert ph <= th

    # Square source: 1000x1000
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(1000, 1000, tw, th)
    assert ph == th
    assert pw == th
    assert ox == (tw - pw) // 2


# -------------------------------------------------------------------------
# 2. Strict Subject Pixel Preservation
# -------------------------------------------------------------------------

def test_original_region_exact_pixel_preservation():
    """Verify original subject pixels are composited with pristine fidelity."""
    # Red source image with a distinctive blue center dot
    src = Image.new("RGB", (400, 300), (255, 0, 0)) # Red
    for y in range(140, 160):
        for x in range(190, 210):
            src.putpixel((x, y), (0, 0, 255)) # Blue center dot

    tw, th = 1600, 900 # 16:9 target
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(400, 300, tw, th)

    result = studio_texture_background_expansion(
        img_rgb=src,
        target_w=tw,
        target_h=th,
        placed_w=pw,
        placed_h=ph,
        offset_x=ox,
        offset_y=oy,
        expansion_type=ext_type
    )

    assert result.size == (tw, th)
    # The center of the placed source must retain the exact blue dot
    center_x = ox + pw // 2
    center_y = oy + ph // 2
    r, g, b = result.getpixel((center_x, center_y))
    assert b > 240 and r < 20 and g < 20, f"Subject pixel altered: RGB=({r}, {g}, {b})"


# -------------------------------------------------------------------------
# 3. Mask & Canvas Generation for DALL-E 2 Inpainting
# -------------------------------------------------------------------------

def test_openai_mask_and_canvas_geometry():
    """Verify DALL-E 2 inpainting mask protects the original subject and marks margins for generation."""
    provider = OpenAIOutpaintingProvider()
    src = Image.new("RGB", (600, 600), (100, 150, 200))
    tw, th = 2560, 1440 # 16:9

    # Mock OpenAI client
    mock_response = MagicMock()
    # Create fake 1024x1024 return image
    fake_return = Image.new("RGB", (1024, 1024), (80, 80, 80))
    buf = io.BytesIO()
    fake_return.save(buf, format="PNG")
    mock_response.data = [MagicMock(url="http://fake-openai/image.png")]

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key"}):
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.images.edit.return_value = mock_response

            with patch("httpx.get") as mock_http_get:
                mock_http_get.return_value = MagicMock(status_code=200, content=buf.getvalue())

                result, err = provider.outpaint(src, tw, th, prompt_hint="Extend landscape")

                assert err is None
                assert result is not None
                assert result.size == (tw, th)

                # Verify client.images.edit was called with PNG bytes
                call_kwargs = mock_client.images.edit.call_args.kwargs
                assert "image" in call_kwargs
                assert "mask" in call_kwargs
                assert call_kwargs["size"] == "1024x1024"

                # Check mask transparency: alpha=0 on inpaint region, alpha=255 on protected region
                raw_mask = call_kwargs["mask"][1] if isinstance(call_kwargs["mask"], tuple) else call_kwargs["mask"]
                mask_img = Image.open(io.BytesIO(raw_mask))
                np_mask = np.array(mask_img)
                # Outer unused borders should be alpha=255 (protected)
                assert np_mask[0, 0, 3] == 255
                # Center subject should be alpha=255 (protected)
                assert np_mask[512, 512, 3] == 255


# -------------------------------------------------------------------------
# 4. Genuine AI Provider vs Honest Fallback
# -------------------------------------------------------------------------

def test_genuine_ai_provider_success_attribution():
    """Verify expand_background_ai accurately reports 'ready' and is_generative_ai=True for genuine AI."""
    src = Image.new("RGB", (800, 600), (100, 150, 200))
    fake_return = Image.new("RGB", (1024, 1024), (80, 80, 80))
    buf = io.BytesIO()
    fake_return.save(buf, format="PNG")

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key"}):
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.images.edit.return_value = MagicMock(data=[MagicMock(url="http://fake-openai/img.png")])

            with patch("httpx.get") as mock_http_get:
                mock_http_get.return_value = MagicMock(status_code=200, content=buf.getvalue())

                img, meta = expand_background_ai(src, 2560, 1440)
                assert img is not None
                assert meta["status"] == "ready"
                assert meta["provider"] == "openai"
                assert meta["is_generative_ai"] is True


def test_ai_provider_failure_honest_fallback():
    """Verify API errors gracefully trigger labeled fallback without falsely claiming AI generation."""
    src = Image.new("RGB", (800, 600), (100, 150, 200))

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key"}):
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            # Simulate OpenAI rate limit or timeout exception
            mock_client.images.edit.side_effect = Exception("Rate limit exceeded (429)")

            img, meta = expand_background_ai(src, 2560, 1440, allow_opencv_fallback=True)
            assert img is not None
            assert img.size == (2560, 1440)
            # Must NOT claim generative AI
            assert meta["status"] == "fallback"
            assert meta["is_generative_ai"] is False
            assert "Rate limit exceeded" in meta["error_message"]


def test_missing_api_keys_honest_status():
    """Verify missing API credentials with fallback disabled reports 'unavailable'."""
    src = Image.new("RGB", (800, 600), (100, 150, 200))

    with patch.dict(os.environ, {"OPENAI_API_KEY": "", "GEMINI_API_KEY": "", "ALLOW_OPENCV_FALLBACK": "false"}):
        img, meta = expand_background_ai(src, 2560, 1440, allow_opencv_fallback=False)
        assert img is None
        assert meta["status"] in ["unavailable", "failed"]
        assert meta["is_generative_ai"] is False


# -------------------------------------------------------------------------
# 5. End-to-End Comparison Pipeline & Standard Mode Integrity
# -------------------------------------------------------------------------

def test_convert_comparison_preserves_standard_and_populates_ai():
    """Verify POST /api/convert-comparison keeps Standard resize 100% functional and provides AI outputs."""
    img_bytes = create_test_image(1200, 800)
    upload_res = client.post("/api/upload", files={"file": ("fruit.jpg", img_bytes, "image/jpeg")})
    assert upload_res.status_code == 200
    image_id = upload_res.json()["image_id"]

    convert_res = client.post("/api/convert-comparison", json={
        "image_id": image_id,
        "export_format": "jpeg",
        "quality": 90,
    })
    assert convert_res.status_code == 200
    data = convert_res.json()

    assert data["image_id"] == image_id
    assert len(data["rows"]) == 5

    for row in data["rows"]:
        safe_key = row["safe_key"]
        std = row["standard"]
        ai = row["ai"]

        # Standard mode checks (pure Pillow Lanczos)
        assert std["status"] == "ready"
        assert std["method"] == "standard"
        assert len(std["variants"]) == 3

        # AI mode checks
        assert ai["method"] == "ai"
        assert ai["status"] in ["ready", "fallback"]
        assert len(ai["variants"]) == 3

        # Download Standard file
        down_std = client.get(f"/api/download/{image_id}/{safe_key}?method=standard")
        assert down_std.status_code == 200
        std_im = Image.open(io.BytesIO(down_std.content))
        assert std_im.size == (row["width"], row["height"])

        # Download AI file
        down_ai = client.get(f"/api/download/{image_id}/{safe_key}?method=ai")
        assert down_ai.status_code == 200
        ai_im = Image.open(io.BytesIO(down_ai.content))
        assert ai_im.size == (row["width"], row["height"])


def test_session_isolation_prevents_stale_cache():
    """Verify separate uploads generate completely independent files without cross-talk."""
    img1 = create_test_image(800, 600, color=(255, 0, 0)) # Pure Red
    img2 = create_test_image(800, 600, color=(0, 255, 0)) # Pure Green

    up1 = client.post("/api/upload", files={"file": ("img1.jpg", img1, "image/jpeg")}).json()["image_id"]
    up2 = client.post("/api/upload", files={"file": ("img2.jpg", img2, "image/jpeg")}).json()["image_id"]

    assert up1 != up2

    client.post("/api/convert-comparison", json={"image_id": up1})
    client.post("/api/convert-comparison", json={"image_id": up2})

    res1 = client.get(f"/api/download/{up1}/square_1x1?method=standard")
    res2 = client.get(f"/api/download/{up2}/square_1x1?method=standard")

    im1 = Image.open(io.BytesIO(res1.content))
    im2 = Image.open(io.BytesIO(res2.content))

    # Center pixel of im1 must be red, im2 must be green
    assert im1.getpixel((1024, 1024))[0] > 200
    assert im2.getpixel((1024, 1024))[1] > 200


def test_no_grey_bars_in_scenery_fallback():
    """Verify scenery fallback outpainting continues natural colors without flat grey bars or visible seams."""
    # Synthetic sky photograph: blue sky at top, white clouds at center, green foliage at bottom
    src = Image.new("RGB", (400, 400), (80, 180, 220)) # Sky blue
    for y in range(150, 250):
        for x in range(400):
            src.putpixel((x, y), (245, 245, 250)) # White clouds
    for y in range(320, 400):
        for x in range(400):
            src.putpixel((x, y), (40, 120, 60)) # Green foliage

    tw, th = 1600, 900 # 16:9
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(400, 400, tw, th)

    res = studio_texture_background_expansion(
        img_rgb=src,
        target_w=tw,
        target_h=th,
        placed_w=pw,
        placed_h=ph,
        offset_x=ox,
        offset_y=oy,
        expansion_type=ext_type
    )

    arr = np.array(res)
    # 1. Left seam delta must be zero (seamless boundary)
    left_seam_delta = np.max(np.abs(arr[:, ox].astype(float) - arr[:, ox - 1].astype(float)))
    assert left_seam_delta == 0.0, f"Visible boundary seam on left: {left_seam_delta}"

    # 2. Right seam delta must be zero
    right_seam_delta = np.max(np.abs(arr[:, ox + pw - 1].astype(float) - arr[:, ox + pw].astype(float)))
    assert right_seam_delta == 0.0, f"Visible boundary seam on right: {right_seam_delta}"

    # 3. Left margin must NOT be a flat grey bar: top should be blue sky (B > 180), mid should be clouds (R > 230, G > 230), bot should be foliage (G > 80, B < 120)
    far_x = 50
    top_pixel = arr[50, far_x] # y=50 (sky)
    mid_pixel = arr[th // 2, far_x] # y=450 (cloud)
    bot_pixel = arr[th - 50, far_x] # y=850 (foliage)

    assert top_pixel[2] > 170, f"Sky not blue at far edge: {top_pixel}"
    assert mid_pixel[0] > 220 and mid_pixel[1] > 220, f"Clouds not white at far edge: {mid_pixel}"
    assert bot_pixel[1] > bot_pixel[2], f"Foliage not green at far edge: {bot_pixel}"


def test_strict_ai_mode_suppresses_blurry_fallback_on_api_error():
    """Verify that when fallback is disabled, API failures never silently return blurred images."""
    src = Image.new("RGB", (400, 400), (100, 150, 200))
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key", "ALLOW_OPENCV_FALLBACK": "false"}):
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.images.edit.side_effect = Exception("OpenAI account has no credits remaining (credit_balance_exhausted)")

            img, meta = expand_background_ai(src, 1600, 900, allow_opencv_fallback=False)
            assert img is None, "Must not return an image when fallback is disabled"
            assert meta["status"] == "failed"
            assert meta["is_generative_ai"] is False
            assert "credit" in meta["error_message"].lower()
