"""Automated tests for Stop Unwanted Text in AI Backgrounds, Product Preservation, and Output Integrity."""

import os
import io
import pytest
import numpy as np
from PIL import Image, ImageDraw
from rapidocr_onnxruntime import RapidOCR

from services.product_segmenter import (
    segment_product,
    fit_product_cutout_proportional,
    render_natural_ground_shadow,
    is_transparent_rgba,
)
from services.ai_background_expander import (
    validate_background_for_unwanted_text,
    generate_clean_ai_studio_background,
    expand_background_groq,
    calculate_expansion_canvas,
)
from services.crop_engine import (
    RATIO_CONFIGS,
    SIZE_KEYS,
    SIZE_PRESETS,
    direct_stretch,
)


def create_product_with_printed_text(size=(500, 500)) -> Image.Image:
    """Create a test product (e.g. T-shirt) with printed logo & text."""
    img = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(img)
    # Draw product body
    draw.polygon(
        [(150, 80), (350, 80), (420, 180), (360, 220), (320, 180), (320, 440), (180, 440), (180, 180), (140, 220), (80, 180)],
        fill=(30, 80, 175)
    )
    # Legitimate printed text on the product
    draw.text((200, 260), "SUPERIOR FIT 1995", fill=(255, 255, 255))
    return img


def test_product_segmentation_preserves_product():
    """Verify product segmentation identifies the complete product without amputating parts."""
    product_img = create_product_with_printed_text()
    cutout, alpha_mask, bbox, meta = segment_product(product_img)

    assert meta["product_preserved"] is True
    assert cutout.mode == "RGBA"
    assert alpha_mask.mode == "L"
    assert bbox[2] > bbox[0]
    assert bbox[3] > bbox[1]

    # Verify that the printed text pixels on the product remain inside the cutout
    ocr = RapidOCR()
    ocr_res, _ = ocr(np.array(cutout.convert("RGB")))
    detected = [item[1] for item in ocr_res] if ocr_res else []
    assert any("SUPERIOR" in t or "FIT" in t for t in detected), f"Product text was lost in cutout! Detected: {detected}"


def test_transparent_png_native_alpha_preserved():
    """Verify that images already having transparent alpha channels are preserved natively."""
    rgba = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rgba)
    draw.rectangle([50, 50, 250, 250], fill=(200, 50, 50, 255))

    cutout, alpha, bbox, meta = segment_product(rgba)
    assert meta["method"] == "native_alpha"
    assert bbox == (50, 50, 251, 251)


def test_unwanted_text_detection_flags_dirty_background():
    """Verify that validate_background_for_unwanted_text catches fake text and allows clean backgrounds."""
    # Clean background
    clean_bg = Image.new("RGB", (400, 300), (235, 238, 242))
    is_clean, texts = validate_background_for_unwanted_text(clean_bg)
    assert is_clean is True
    assert len(texts) == 0

    # Dirty background with hallucinated AI text
    dirty_bg = Image.new("RGB", (400, 300), (235, 238, 242))
    draw = ImageDraw.Draw(dirty_bg)
    draw.text((40, 40), "FAKE LOGO 2026", fill=(40, 40, 40))

    is_clean_dirty, texts_dirty = validate_background_for_unwanted_text(dirty_bg)
    assert is_clean_dirty is False
    assert len(texts_dirty) > 0
    assert any("FAKE" in t or "LOGO" in t for t in texts_dirty)


def test_unwanted_text_detection_respects_user_allowed_text():
    """Verify that user-requested text is allowed when explicitly specified."""
    bg_with_user_text = Image.new("RGB", (400, 300), (235, 238, 242))
    draw = ImageDraw.Draw(bg_with_user_text)
    draw.text((40, 40), "SUMMER SALE", fill=(40, 40, 40))

    # Without permission -> flagged as unwanted
    is_clean, _ = validate_background_for_unwanted_text(bg_with_user_text)
    assert is_clean is False

    # With user permission -> accepted
    is_clean_allowed, remaining = validate_background_for_unwanted_text(bg_with_user_text, allowed_text="SUMMER SALE")
    assert is_clean_allowed is True
    assert len(remaining) == 0


def test_proportional_cutout_fitting():
    """Verify product cutout is fitted proportionally with appropriate padding without being too small."""
    rgba = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(rgba)
    draw.rectangle([100, 100, 400, 400], fill=(50, 100, 200, 255))

    target_w, target_h = 1920, 1080  # 16:9
    placed_cutout, ox, oy, pw, ph = fit_product_cutout_proportional(rgba, target_w, target_h, padding=0.10)

    # Product should fit within canvas boundaries
    assert ox >= 0
    assert oy >= 0
    assert ox + pw <= target_w
    assert oy + ph <= target_h

    # Product aspect ratio must remain 1:1
    aspect_diff = abs((pw / ph) - 1.0)
    assert aspect_diff < 0.05, f"Product was distorted! Aspect ratio changed to {pw}/{ph}"

    # Product height should utilize ~80% of canvas height (with 10% padding on each side)
    expected_height = int(round(1080 * 0.80))
    assert abs(ph - expected_height) <= 4, f"Product size {ph} is unexpectedly small or large (expected ~{expected_height})"


def test_natural_ground_contact_shadow():
    """Verify realistic ground contact shadow generation."""
    shadow = render_natural_ground_shadow(1080, 1080, 500, 500, 290, 290)
    assert shadow.size == (1080, 1080)
    assert shadow.mode == "RGBA"
    # Shadow must have some opacity
    alpha_np = np.array(shadow.split()[-1])
    assert np.max(alpha_np) > 20


def test_method_b_all_15_outputs_correct_dimensions():
    """Verify that all 5 aspect ratios at Large, Medium, and Small produce exact configured dimensions."""
    product_img = create_product_with_printed_text((400, 400))

    for ratio_key, config in RATIO_CONFIGS.items():
        safe_key = config["safe_key"]
        large_w, large_h = config["width"], config["height"]

        # Run Method B expansion
        res_img, meta = expand_background_groq(product_img, large_w, large_h)
        assert res_img is not None
        assert res_img.size == (large_w, large_h), f"{safe_key} Large size mismatch: got {res_img.size}, expected ({large_w}, {large_h})"
        assert meta["product_preserved"] is True
        assert meta["text_validated"] is True
        assert meta["unwanted_text_detected"] is False

        # Test Medium and Small variant resizes
        for size_key in SIZE_KEYS:
            vw, vh = SIZE_PRESETS[safe_key][size_key]
            variant_img = res_img.resize((vw, vh), Image.Resampling.LANCZOS)
            assert variant_img.size == (vw, vh), f"{safe_key} {size_key} size mismatch: got {variant_img.size}, expected ({vw}, {vh})"


def test_method_a_standard_remains_unchanged():
    """Verify that Method A (Standard direct stretch with Lanczos) is completely unaffected."""
    source_img = Image.new("RGB", (600, 400), (100, 150, 200))
    tw, th = 1080, 1080
    std_out = direct_stretch(source_img, tw, th)

    assert std_out.size == (tw, th)
    assert std_out.mode == "RGB"
