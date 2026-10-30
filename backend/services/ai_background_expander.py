"""Product-Safe AI & Commercial Studio Background Expansion Service for Ratio Studio.
Maintains 100% pixel fidelity for jewellery, products, vehicles, landscapes, and portraits.

Features:
1. Cloudflare Workers AI Inpainting: Uses @cf/runwayml/stable-diffusion-v1-5-inpainting with
   configurable width/height matching the exact aspect ratio of each target preset (1:1, 4:5, 3:4, 16:9, 5:4).
2. Aspect-Ratio-Preserving Canvas Construction: No squeezing into 512x512, no compositional distortion.
3. Strict Subject Protection: Composites pristine customer-approved cropped image over generated background.
4. Honest Status & Fallback Reporting:
   - 'ready' with provider 'cloudflare_workers_ai' and is_generative_ai=True only when generation succeeds.
   - 'fallback' with provider 'studio_fallback' and is_generative_ai=False when AI is unavailable.
   - Never mislabels OpenCV fallback as generative AI.
"""

import os
import io
import math
import time
import json
import base64
import logging
from typing import Optional, Tuple, Dict, Any, List
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageDraw

logger = logging.getLogger(__name__)

# Load environment variables from backend/.env if present
try:
    import dotenv
    _curr_dir = os.path.dirname(os.path.abspath(__file__))
    _backend_dir = os.path.dirname(_curr_dir)
    for _ep in [os.path.join(_backend_dir, '.env'), os.path.join(os.path.dirname(_backend_dir), '.env'), '.env']:
        if os.path.exists(_ep):
            dotenv.load_dotenv(_ep, override=False)
            break
except Exception:
    pass

from services.groq_vision import (
    analyze_scene_for_background_expansion,
    is_groq_enabled,
)


def is_cloudflare_enabled() -> bool:
    """Check if Cloudflare Workers AI credentials are configured."""
    return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID")) and bool(os.environ.get("CLOUDFLARE_API_TOKEN"))


def get_configured_ai_provider() -> str:
    """Check which AI/expansion provider is configured in environment."""
    try:
        import dotenv
        dotenv.load_dotenv(override=True)
    except Exception:
        pass

    if is_cloudflare_enabled():
        return "cloudflare"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    return "studio"


def get_model_working_dimensions(target_w: int, target_h: int) -> Tuple[int, int]:
    """
    Return model-compatible dimensions preserving the target aspect ratio.
    Dimensions are multiples of 8 (required by SD 1.5 inpainting).
    """
    ratio = target_w / float(target_h)
    if abs(ratio - 1.0) < 0.05:             # 1:1 Square (2048x2048)
        return 768, 768
    elif abs(ratio - (4.0 / 5.0)) < 0.05:   # 4:5 Portrait (1600x2000)
        return 640, 800
    elif abs(ratio - (3.0 / 4.0)) < 0.05:   # 3:4 Portrait (1536x2048)
        return 768, 1024
    elif abs(ratio - (16.0 / 9.0)) < 0.05:  # 16:9 Landscape (2560x1440)
        return 1024, 576
    elif abs(ratio - (5.0 / 4.0)) < 0.05:   # 5:4 Landscape (2000x1600)
        return 1000, 800
    else:
        # Generic computation preserving aspect ratio, multiple of 8
        if ratio >= 1.0:
            w = 1024
            h = max(256, (int(round(1024 / ratio)) // 8) * 8)
        else:
            h = 1024
            w = max(256, (int(round(1024 * ratio)) // 8) * 8)
        return w, h


def calculate_expansion_canvas(
    orig_w: int,
    orig_h: int,
    target_w: int,
    target_h: int,
    source_img: Optional[Image.Image] = None,
) -> Tuple[int, int, int, int, str]:
    """
    Calculate proportional placement of source image within target canvas.
    Returns: (placed_w, placed_h, offset_x, offset_y, expansion_type)
    expansion_type is one of: 'none', 'horizontal', 'vertical'.
    """
    target_ratio = target_w / float(target_h)
    orig_ratio = orig_w / float(orig_h)

    # If aspect ratios are virtually identical (within 1%)
    if abs(orig_ratio - target_ratio) / target_ratio < 0.01:
        return target_w, target_h, 0, 0, "none"

    if orig_ratio < target_ratio:
        # Target is wider than source -> needs horizontal extension (left & right)
        scale = target_h / float(orig_h)
        placed_h = target_h
        placed_w = max(1, int(round(orig_w * scale)))
        if placed_w > target_w:
            placed_w = target_w
        offset_x = (target_w - placed_w) // 2
        offset_y = 0
        return placed_w, placed_h, offset_x, offset_y, "horizontal"
    else:
        # Target is taller than source -> needs vertical extension (top & bottom)
        scale = target_w / float(orig_w)
        placed_w = target_w
        placed_h = max(1, int(round(orig_h * scale)))
        if placed_h > target_h:
            placed_h = target_h
        offset_x = 0

        # Check if bottom of subject is cut off by comparing variance
        bottom_cut_off = False
        if source_img is not None:
            try:
                np_src = np.array(source_img.convert("RGB"))
                top_v = float(np.var(np_src[:12, :, :]))
                bot_v = float(np.var(np_src[-12:, :, :]))
                if bot_v > top_v * 1.5 and bot_v > 1500.0:
                    bottom_cut_off = True
            except Exception:
                pass

        if bottom_cut_off:
            offset_y = target_h - placed_h  # Align to bottom frame naturally
        else:
            offset_y = (target_h - placed_h) // 2
        return placed_w, placed_h, offset_x, offset_y, "vertical"


def composite_protected_foreground(
    background_img: Image.Image,
    foreground_img: Image.Image,
    target_w: int,
    target_h: int,
    orig_w: int,
    orig_h: int,
    source_img_for_geometry: Optional[Image.Image] = None,
    feather_radius: Optional[int] = None,
) -> Image.Image:
    """
    Composite the protected foreground image over the generated background.
    - Preserves aspect ratio and proportional framing.
    - Uses anti-aliased cosine feathering at the boundaries to prevent sharp rectangular cut seams.
    - Handles RGBA transparency seamlessly without fringing.
    - Works with either the original approved working.png or a Real-ESRGAN enhanced foreground.
    """
    final_pw, final_ph, final_ox, final_oy, _ = calculate_expansion_canvas(
        orig_w, orig_h, target_w, target_h, source_img=source_img_for_geometry or foreground_img
    )

    placed_fg = foreground_img.resize((final_pw, final_ph), Image.Resampling.LANCZOS)
    is_rgba = (placed_fg.mode == "RGBA")

    if feather_radius is None:
        feather = min(14, max(4, min(final_pw, final_ph) // 25))
    else:
        feather = feather_radius

    if is_rgba:
        result = background_img.copy()
        alpha = placed_fg.split()[-1]
        result.paste(placed_fg.convert("RGB"), (final_ox, final_oy), mask=alpha)
        return result

    # Outer-boundary seam blending: blend strictly OUTSIDE the protected source rectangle
    # so 100% of the placed source rectangle pixels remain untouched by feathering.
    bg_np = np.array(background_img.convert("RGB"), dtype=np.float32)
    fg_np = np.array(placed_fg.convert("RGB"), dtype=np.float32)

    if feather > 1:
        # Left outer seam (in background region x < final_ox)
        if final_ox > 0:
            span = min(feather, final_ox)
            left_edge = fg_np[:, 0, :]
            for d in range(1, span + 1):
                w = 0.5 * (1.0 - np.cos(np.pi * d / (span + 1)))
                x = final_ox - d
                bg_np[final_oy:final_oy + final_ph, x, :] = (
                    (1.0 - w) * left_edge + w * bg_np[final_oy:final_oy + final_ph, x, :]
                )
        # Right outer seam (in background region x >= final_ox + final_pw)
        right_space = target_w - (final_ox + final_pw)
        if right_space > 0:
            span = min(feather, right_space)
            right_edge = fg_np[:, -1, :]
            for d in range(1, span + 1):
                w = 0.5 * (1.0 - np.cos(np.pi * d / (span + 1)))
                x = final_ox + final_pw - 1 + d
                bg_np[final_oy:final_oy + final_ph, x, :] = (
                    (1.0 - w) * right_edge + w * bg_np[final_oy:final_oy + final_ph, x, :]
                )
        # Top outer seam (in background region y < final_oy)
        if final_oy > 0:
            span = min(feather, final_oy)
            top_edge = fg_np[0, :, :]
            for d in range(1, span + 1):
                w = 0.5 * (1.0 - np.cos(np.pi * d / (span + 1)))
                y = final_oy - d
                bg_np[y, final_ox:final_ox + final_pw, :] = (
                    (1.0 - w) * top_edge + w * bg_np[y, final_ox:final_ox + final_pw, :]
                )
        # Bottom outer seam (in background region y >= final_oy + final_ph)
        bottom_space = target_h - (final_oy + final_ph)
        if bottom_space > 0:
            span = min(feather, bottom_space)
            bot_edge = fg_np[-1, :, :]
            for d in range(1, span + 1):
                w = 0.5 * (1.0 - np.cos(np.pi * d / (span + 1)))
                y = final_oy + final_ph - 1 + d
                bg_np[y, final_ox:final_ox + final_pw, :] = (
                    (1.0 - w) * bot_edge + w * bg_np[y, final_ox:final_ox + final_pw, :]
                )

    # Paste complete protected source rectangle with zero internal feathering
    bg_np[final_oy:final_oy + final_ph, final_ox:final_ox + final_pw, :] = fg_np
    result = Image.fromarray(np.clip(bg_np, 0, 255).round().astype(np.uint8))

    return result


def studio_texture_background_expansion(
    img_rgb: Image.Image,
    target_w: int,
    target_h: int,
    placed_w: int,
    placed_h: int,
    offset_x: int,
    offset_y: int,
    expansion_type: str = "none",
    bg_color_hex: str = "#F8FAFC",
    is_transparent: bool = False,
    vision_info: Optional[Dict[str, Any]] = None,
    foreground_img: Optional[Image.Image] = None,
    **kwargs
) -> Image.Image:
    """
    High-fidelity stripe-free background expansion:
    1. Uniform/Studio backdrops: Extends seamless matching studio tone.
    2. Scenery/Photographs: Uses edge-replicated multi-scale atmospheric diffusion:
       - Never mirrors thin strips (no accordion barcode scanlines, comb ripples, or repeating patterns).
       - Uses 2D Gaussian blur + cubic Hermite blending to ensure smooth monotonic gradient transitions.
       - Composites pristine original source pixels with anti-aliased smooth feathering.
    """
    is_rgba = (img_rgb.mode == "RGBA")
    if is_transparent and is_rgba:
        placed_img = img_rgb.resize((placed_w, placed_h), resample=Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        canvas.paste(placed_img, (offset_x, offset_y), mask=placed_img.split()[-1])
        return canvas

    clean_img = img_rgb.convert("RGB")
    placed_img = clean_img.resize((placed_w, placed_h), resample=Image.Resampling.LANCZOS)
    placed_np = np.array(placed_img)

    pad_top = max(0, offset_y)
    pad_bottom = max(0, target_h - offset_y - placed_h)
    pad_left = max(0, offset_x)
    pad_right = max(0, target_w - offset_x - placed_w)

    if pad_top == 0 and pad_bottom == 0 and pad_left == 0 and pad_right == 0:
        if placed_img.size != (target_w, target_h):
            return placed_img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
        return placed_img

    info = vision_info or {}
    scene_type = info.get("scene_type", "scenery")

    # Analyze perimeter color variance to distinguish uniform studio backdrops from scenery
    bw = max(2, min(16, min(placed_w, placed_h) // 20))
    perim_samples = np.concatenate([
        placed_np[:bw, :, :].reshape(-1, 3),
        placed_np[-bw:, :, :].reshape(-1, 3),
        placed_np[:, :bw, :].reshape(-1, 3),
        placed_np[:, -bw:, :].reshape(-1, 3)
    ], axis=0)
    perim_std = float(np.mean(np.std(perim_samples.astype(np.float32), axis=0)))
    perim_median = np.median(perim_samples, axis=0).astype(int)

    custom_bg = None
    if bg_color_hex and bg_color_hex.upper() not in ["#F8FAFC", ""]:
        hex_clean = bg_color_hex.lstrip("#")
        if len(hex_clean) == 6:
            try:
                custom_bg = tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
            except Exception:
                custom_bg = None

    canvas_np = np.zeros((target_h, target_w, 3), dtype=np.uint8)

    # Handle solid/studio backgrounds
    if custom_bg is not None or scene_type in ["studio_solid", "graphic"] or perim_std < 5.0:
        fill_color = custom_bg if custom_bg is not None else tuple(int(c) for c in perim_median)
        canvas_np[:, :] = fill_color
    else:
        # Edge-replicated border canvas (eliminates periodic accordion barcode scanlines completely!)
        # Neutralize outermost 2px border rows/cols before edge replication
        # If the input image has tiny watermarks or stock codes at the edge (e.g. "...84686"),
        # this prevents replicating them into the inpainting canvas.
        placed_np_clean = placed_np.copy()
        if pad_bottom > 0 and placed_h > 6:
            placed_np_clean[-2:, :] = cv2.medianBlur(placed_np[-4:-2, :], 5)
        if pad_top > 0 and placed_h > 6:
            placed_np_clean[:2, :] = cv2.medianBlur(placed_np[2:4, :], 5)
        if pad_left > 0 and placed_w > 6:
            placed_np_clean[:, :2] = cv2.medianBlur(placed_np[:, 2:4], 5)
        if pad_right > 0 and placed_w > 6:
            placed_np_clean[:, -2:] = cv2.medianBlur(placed_np[:, -4:-2], 5)

        canvas_np = cv2.copyMakeBorder(placed_np_clean, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REPLICATE)

        # Multi-scale atmospheric diffusion across expansion wings
        kw = max(31, ((pad_left + pad_right) // 3) | 1) if (pad_left + pad_right) > 0 else 31
        kh = max(31, ((pad_top + pad_bottom) // 3) | 1) if (pad_top + pad_bottom) > 0 else 31
        diffused = cv2.GaussianBlur(canvas_np, (kw, kh), 0)

        # Hermite smoothstep blend on wings
        if pad_left > 0:
            t = np.linspace(1.0, 0.0, pad_left, dtype=np.float32)
            w_b = (t * t * (3.0 - 2.0 * t))[None, :, None]
            canvas_np[:, :pad_left] = (
                canvas_np[:, :pad_left].astype(np.float32) * (1.0 - w_b * 0.95) +
                diffused[:, :pad_left].astype(np.float32) * (w_b * 0.95)
            ).astype(np.uint8)

        if pad_right > 0:
            t = np.linspace(0.0, 1.0, pad_right, dtype=np.float32)
            w_b = (t * t * (3.0 - 2.0 * t))[None, :, None]
            canvas_np[:, target_w - pad_right:] = (
                canvas_np[:, target_w - pad_right:].astype(np.float32) * (1.0 - w_b * 0.95) +
                diffused[:, target_w - pad_right:].astype(np.float32) * (w_b * 0.95)
            ).astype(np.uint8)

        if pad_top > 0:
            t = np.linspace(1.0, 0.0, pad_top, dtype=np.float32)
            w_b = (t * t * (3.0 - 2.0 * t))[:, None, None]
            canvas_np[:pad_top, :] = (
                canvas_np[:pad_top, :].astype(np.float32) * (1.0 - w_b * 0.95) +
                diffused[:pad_top, :].astype(np.float32) * (w_b * 0.95)
            ).astype(np.uint8)

        if pad_bottom > 0:
            t = np.linspace(0.0, 1.0, pad_bottom, dtype=np.float32)
            w_b = (t * t * (3.0 - 2.0 * t))[:, None, None]
            canvas_np[target_h - pad_bottom:, :] = (
                canvas_np[target_h - pad_bottom:, :].astype(np.float32) * (1.0 - w_b * 0.95) +
                diffused[target_h - pad_bottom:, :].astype(np.float32) * (w_b * 0.95)
            ).astype(np.uint8)

    # 3. Separate background generation from protected foreground compositing
    res_img = Image.fromarray(canvas_np)
    effective_fg = foreground_img if foreground_img is not None else placed_img
    return composite_protected_foreground(
        background_img=res_img,
        foreground_img=effective_fg,
        target_w=target_w,
        target_h=target_h,
        orig_w=placed_w if expansion_type == "none" else clean_img.size[0],
        orig_h=placed_h if expansion_type == "none" else clean_img.size[1],
        source_img_for_geometry=clean_img,
    )


def call_groq_vision_guided_expansion(
    source_img: Image.Image,
    target_w: int,
    target_h: int,
    prompt: Optional[str] = None,
    vision_info: Optional[Dict[str, Any]] = None,
    bg_color_hex: str = "#F8FAFC",
    is_transparent: bool = False,
) -> Tuple[Optional[Image.Image], Optional[Dict[str, Any]], Optional[str]]:
    """
    Executes Groq Vision analysis (or uses cached vision_info) and performs
    intelligent studio background expansion.
    Returns: (expanded_image, vision_info, error_message)
    """
    try:
        if vision_info is None:
            vision_info = analyze_scene_for_background_expansion(source_img)

        w, h = source_img.size
        pw, ph, ox, oy, ext_type = calculate_expansion_canvas(w, h, target_w, target_h, source_img=source_img)

        expanded = studio_texture_background_expansion(
            img_rgb=source_img,
            target_w=target_w,
            target_h=target_h,
            placed_w=pw,
            placed_h=ph,
            offset_x=ox,
            offset_y=oy,
            expansion_type=ext_type,
            bg_color_hex=bg_color_hex,
            is_transparent=is_transparent,
            vision_info=vision_info,
        )
        return expanded, vision_info, None

    except Exception as e:
        return None, None, f"Groq vision-assisted expansion error: {str(e)[:120]}"


def call_cloudflare_workers_ai_inpainting(
    source_img: Image.Image,
    target_w: int,
    target_h: int,
    prompt: Optional[str] = None,
    vision_info: Optional[Dict[str, Any]] = None,
    bg_color_hex: Optional[str] = None,
    is_transparent: bool = False,
    foreground_img: Optional[Image.Image] = None,
) -> Tuple[Optional[Image.Image], Optional[str]]:
    """
    Call Cloudflare Workers AI inpainting model with model-compatible dimensions
    preserving the target aspect ratio (no 512x512 squeezing).
    Features:
    1. Atmospheric pre-diffused outer wings: prevents duplicate subject hallucinations (extra butterflies/birds/wheels).
    2. Comprehensive scene-aware prompt + strict negative prompt: prevents tripods, marble tiles, mountains, and black bars.
    3. Blank/black output guard: automatically rejects filtered or corrupted all-black frames.
    4. Anti-aliased cosine-feathered blending: eliminates harsh rectangular cut seams.
    5. Preserves pristine customer-approved cropped image at 100% resolution.
    Returns: (generated_image, error_message)
    """
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not api_token:
        return None, "Cloudflare credentials not configured in backend/.env"

    try:
        import requests
        from services.groq_vision import _local_scene_heuristic

        orig_w, orig_h = source_img.size
        # 1. Aspect-ratio preserving working dimensions (multiples of 8)
        work_w, work_h = get_model_working_dimensions(target_w, target_h)

        # 2. Placement within working dimensions
        pw, ph, ox, oy, ext_type = calculate_expansion_canvas(
            orig_w, orig_h, work_w, work_h, source_img=source_img
        )

        if ox == 0 and oy == 0:
            return source_img.resize((target_w, target_h), Image.Resampling.LANCZOS), None

        placed_src = source_img.resize((pw, ph), Image.Resampling.LANCZOS)
        placed_np = np.array(placed_src)

        pad_left, pad_right = ox, max(0, work_w - (ox + pw))
        pad_top, pad_bottom = oy, max(0, work_h - (oy + ph))

        # Extract scene information for accurate prompt, negative prompt, and canvas pre-filling
        scene_info = vision_info or _local_scene_heuristic(source_img)

        # Sample background colors from four corners of placed_src (corners avoid foreground subjects)
        c_size = max(4, min(32, min(pw, ph) // 8))
        tl = np.median(placed_np[:c_size, :c_size], axis=(0, 1)).astype(np.float32)
        tr = np.median(placed_np[:c_size, -c_size:], axis=(0, 1)).astype(np.float32)
        bl = np.median(placed_np[-c_size:, :c_size], axis=(0, 1)).astype(np.float32)
        br = np.median(placed_np[-c_size:, -c_size:], axis=(0, 1)).astype(np.float32)

        def parse_hex_color(h_str, fallback):
            if isinstance(h_str, str):
                c = h_str.strip().lstrip("#")
                if len(c) == 6:
                    try:
                        return np.array([int(c[i:i+2], 16) for i in (0, 2, 4)], dtype=np.float32)
                    except Exception:
                        pass
            return fallback

        top_rgb = parse_hex_color(scene_info.get("top_color_hex"), (tl + tr) * 0.5)
        bot_rgb = parse_hex_color(scene_info.get("bottom_color_hex"), (bl + br) * 0.5)
        dom_rgb = parse_hex_color(scene_info.get("dominant_bg_hex"), (top_rgb + bot_rgb) * 0.5)

        # 3. Canvas setup: Pre-fill extended canvas with clean ambient background tone / lighting gradient.
        # This completely prevents smearing sliced subject pieces (e.g. shoe soles, laces, t-shirt graphics)
        # into outer wings, stopping the inpainting model from hallucinating duplicate shoes or extra cars!
        yy = np.linspace(0.0, 1.0, work_h, dtype=np.float32)[:, None, None]
        xx = np.linspace(0.0, 1.0, work_w, dtype=np.float32)[None, :, None]
        top_row = (1.0 - xx) * tl + xx * tr
        bot_row = (1.0 - xx) * bl + xx * br
        ambient_canvas = (1.0 - yy) * top_row + yy * bot_row
        canvas_np = np.clip(ambient_canvas, 0, 255).astype(np.uint8)

        # Place the subject image at its target coordinates
        canvas_np[oy : oy + ph, ox : ox + pw] = placed_np

        # Soft 10px boundary blend outside the placed image so inpainting has a smooth boundary
        blend_span = 10
        if pad_left > 0:
            span = min(blend_span, pad_left)
            left_col = placed_np[:, 0, :].astype(np.float32)
            for d in range(1, span + 1):
                w_blend = 0.5 * (1.0 + np.cos(np.pi * d / (span + 1)))
                x = ox - d
                canvas_np[oy : oy + ph, x, :] = np.clip(
                    w_blend * left_col + (1.0 - w_blend) * canvas_np[oy : oy + ph, x, :].astype(np.float32), 0, 255
                ).astype(np.uint8)

        if pad_right > 0:
            span = min(blend_span, pad_right)
            right_col = placed_np[:, -1, :].astype(np.float32)
            for d in range(1, span + 1):
                w_blend = 0.5 * (1.0 + np.cos(np.pi * d / (span + 1)))
                x = ox + pw - 1 + d
                canvas_np[oy : oy + ph, x, :] = np.clip(
                    w_blend * right_col + (1.0 - w_blend) * canvas_np[oy : oy + ph, x, :].astype(np.float32), 0, 255
                ).astype(np.uint8)

        if pad_top > 0:
            span = min(blend_span, pad_top)
            top_row_pix = placed_np[0, :, :].astype(np.float32)
            for d in range(1, span + 1):
                w_blend = 0.5 * (1.0 + np.cos(np.pi * d / (span + 1)))
                y = oy - d
                canvas_np[y, ox : ox + pw, :] = np.clip(
                    w_blend * top_row_pix + (1.0 - w_blend) * canvas_np[y, ox : ox + pw, :].astype(np.float32), 0, 255
                ).astype(np.uint8)

        if pad_bottom > 0:
            span = min(blend_span, pad_bottom)
            bot_row_pix = placed_np[-1, :, :].astype(np.float32)
            for d in range(1, span + 1):
                w_blend = 0.5 * (1.0 + np.cos(np.pi * d / (span + 1)))
                y = oy + ph - 1 + d
                canvas_np[y, ox : ox + pw, :] = np.clip(
                    w_blend * bot_row_pix + (1.0 - w_blend) * canvas_np[y, ox : ox + pw, :].astype(np.float32), 0, 255
                ).astype(np.uint8)

        canvas = Image.fromarray(canvas_np)

        # 4. Inpainting mask: 255 (generate) on the extended canvas, 0 (protect) on original subject
        # Include a 6px transition overlap so the inpainting boundary merges seamlessly
        mask_np = np.zeros((work_h, work_w), dtype=np.uint8)
        seam_overlap = 6
        if pad_top > 0:
            mask_np[:pad_top + seam_overlap, :] = 255
        if pad_bottom > 0:
            mask_np[work_h - pad_bottom - seam_overlap:, :] = 255
        if pad_left > 0:
            mask_np[:, :pad_left + seam_overlap] = 255
        if pad_right > 0:
            mask_np[:, work_w - pad_right - seam_overlap:] = 255
        mask = Image.fromarray(mask_np)

        # 5. Extract scene information and construct prompt and negative prompt
        subject_desc = str(scene_info.get("subject_description", "")).strip()
        scene_type = str(scene_info.get("scene_type", "scenery")).strip()
        ext_advice = str(scene_info.get("extension_advice", "")).strip()
        has_sky = bool(scene_info.get("has_sky"))
        has_ground = bool(scene_info.get("has_ground_or_water"))

        # Negative prompt: Front-loaded with strict anti-text, anti-watermark, and anti-duplicate-subject tokens
        universal_negative = (
            "text, words, letters, numbers, digits, font, typography, writing, watermark, "
            "signature, stamp, logo, label, brand mark, copyright, serial number, barcode, "
            "subtitles, caption, quote, headline, advertisement, poster, signage, "
            "duplicate subject, extra subjects, multiple subjects, second object, duplicate product, "
            "duplicate shoes, extra shoe, 3rd shoe, multiple shoes, extra sneakers, footwear, feet, legs, socks, toes, laces, shoe box, "
            "car, vehicle, automobile, miniature car, driving car, wheels, tires, sports car, racing car, "
            "duplicate person, extra person, second person, human, face, hands, arms, body parts, limbs, extra clothing, "
            "mountains, rocky terrain, unrelated scenery, landscape, trees, buildings, "
            "tripod, camera equipment, studio lights, softbox, stand, umbrella, lamps, furniture, "
            "border, black bars, dark frame, seam, split screen, collage, multi-panel, distortion, blur artifacts, messy"
        )

        if prompt:
            final_prompt = f"{prompt}, seamless clean matching background continuation, empty backdrop, completely free of text, words, logos or extra objects, commercial photography, 8k"
            final_negative = universal_negative
        else:
            if scene_type in ["studio_solid", "studio_gradient"] or np.std(top_rgb) < 14.0:
                env_prompt = "seamless clean minimal studio backdrop, smooth empty studio wall and surface, soft diffused ambient lighting, empty background"
            elif has_sky or (top_rgb[2] > top_rgb[0] * 1.05 and top_rgb[2] > 95):
                env_prompt = "soft natural sky with smooth diffused light clouds, out of focus matching environment, clean seamless empty backdrop, soft ambient lighting"
            elif top_rgb[1] > top_rgb[0] * 1.04 and top_rgb[1] > top_rgb[2]:
                env_prompt = "soft blurred natural garden foliage bokeh, delicate warm outdoor morning lighting, seamless clean empty backdrop"
            elif has_ground:
                env_prompt = "matching ground surface and clean blurred background environment, smooth natural surface continuation, soft natural lighting, empty space"
            else:
                env_prompt = "soft out of focus bokeh backdrop, smooth natural color continuation, diffused lighting, clean empty background"

            clean_advice = ext_advice
            if any(forbidden in clean_advice.lower() for forbidden in ["car", "vehicle", "shoe", "text", "draw", "person"]):
                clean_advice = ""

            if clean_advice and len(clean_advice) > 5:
                final_prompt = f"{env_prompt}, {clean_advice}, empty background, no extra objects, completely free of text or watermarks, commercial photography, photorealistic"
            else:
                final_prompt = f"{env_prompt}, clean seamless continuation, empty background, no extra objects, completely free of text or watermarks, commercial photography, photorealistic"

            final_negative = universal_negative
        buf_i, buf_m = io.BytesIO(), io.BytesIO()
        canvas.save(buf_i, format="PNG")
        mask.save(buf_m, format="PNG")

        model_name = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_name}"
        headers = {"Authorization": f"Bearer {api_token}"}
        payload = {
            "prompt": final_prompt,
            "negative_prompt": final_negative,
            "image": list(buf_i.getvalue()),
            "mask": list(buf_m.getvalue()),
            "width": work_w,
            "height": work_h,
        }

        res = requests.post(url, headers=headers, json=payload, timeout=35.0)
        if res.status_code != 200:
            return None, f"Cloudflare API returned status {res.status_code}: {res.text[:120]}"

        gen_img = Image.open(io.BytesIO(res.content)).convert("RGB")
        gen_arr = np.array(gen_img)

        # Post-generation RapidOCR safety guard: detect and erase any hallucinated text in the newly generated wings
        try:
            from rapidocr_onnxruntime import RapidOCR
            ocr_engine = RapidOCR()
            ocr_res, _ = ocr_engine(gen_arr)
            if ocr_res:
                text_mask = np.zeros(gen_arr.shape[:2], dtype=np.uint8)
                found_wing_text = False
                for item in ocr_res:
                    if not item or len(item) < 2:
                        continue
                    pts = np.array(item[0], dtype=np.int32)
                    # Check if text box is in outer wings (outside original subject rectangle)
                    x_min, y_min = np.min(pts[:, 0]), np.min(pts[:, 1])
                    x_max, y_max = np.max(pts[:, 0]), np.max(pts[:, 1])
                    is_in_wing = (
                        (pad_left > 0 and x_min < ox + 12) or
                        (pad_right > 0 and x_max > ox + pw - 12) or
                        (pad_top > 0 and y_min < oy + 12) or
                        (pad_bottom > 0 and y_max > oy + ph - 12)
                    )
                    if is_in_wing:
                        cv2.fillPoly(text_mask, [pts], 255)
                        found_wing_text = True

                if found_wing_text:
                    # Dilate mask and inpaint to seamlessly erase unwanted background text
                    text_mask = cv2.dilate(text_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)), iterations=2)
                    gen_arr = cv2.inpaint(gen_arr, text_mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
                    gen_img = Image.fromarray(gen_arr)
        except Exception as ocr_err:
            logger.debug(f"OCR background text cleanup skipped: {ocr_err}")

        # Guard: check for blank/black output (e.g. NSFW safety filter or model error)
        if float(np.mean(gen_arr)) < 6.0:
            return None, "Cloudflare API returned blank/black frame (filtered). Falling back to studio expansion."

        # 6. Scale generated background to final target dimensions
        final_bg = gen_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # 7. Separate background generation from protected foreground compositing
        effective_fg = foreground_img if foreground_img is not None else source_img
        final_img = composite_protected_foreground(
            background_img=final_bg,
            foreground_img=effective_fg,
            target_w=target_w,
            target_h=target_h,
            orig_w=orig_w,
            orig_h=orig_h,
            source_img_for_geometry=source_img,
        )
        return final_img, None

    except Exception as e:
        return None, f"Cloudflare inpainting error: {str(e)[:120]}"
def expand_background_groq(
    img: Image.Image,
    target_w: int,
    target_h: int,
    prompt_hint: Optional[str] = None,
    cached_analysis: Optional[Any] = None,
    bg_color_hex: str = "#F8FAFC",
    is_transparent: bool = False,
    allow_opencv_fallback: bool = True,
    foreground_img: Optional[Image.Image] = None,
    foreground_mode: str = "original",
    **kwargs
) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
    """
    Method B: AI Background Outpainting.
    Uses genuine Cloudflare Workers AI Inpainting model preserving the exact target aspect ratio.
    If unavailable, uses honest fallback attribution.
    """
    orig_w, orig_h = img.size
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(orig_w, orig_h, target_w, target_h, source_img=img)

    if ext_type == "none":
        effective_fg = foreground_img if foreground_img is not None else img
        resized = effective_fg.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
        meta = {
            "status": "ready",
            "method": "ai",
            "provider": "direct_fit",
            "is_generative_ai": False,
            "canvas_size": [target_w, target_h],
            "placed_box": [0, 0, target_w, target_h],
            "product_preserved": True,
            "foreground_mode": foreground_mode,
            "foreground_fidelity": "pixel_identical" if foreground_mode == "original" else "ai_enhanced_detail",
            "foreground_status": "original_approved" if foreground_mode == "original" else "realesrgan_enhanced",
            "foreground_description": (
                "Original customer-approved pixels preserved without alteration."
                if foreground_mode == "original"
                else "Real-ESRGAN CNN super-resolution enhanced foreground for improved apparent detail. Not claimed to be pixel-identical to source."
            ),
            "error_message": None,
        }
        return resized, meta

    # 1. Attempt genuine generative AI inpainting if Cloudflare credentials are configured
    if is_cloudflare_enabled():
        cf_img, cf_err = call_cloudflare_workers_ai_inpainting(
            source_img=img,
            target_w=target_w,
            target_h=target_h,
            prompt=prompt_hint,
            vision_info=cached_analysis,
            bg_color_hex=bg_color_hex,
            is_transparent=is_transparent,
            foreground_img=foreground_img,
        )
        if cf_img is not None:
            return cf_img, {
                "status": "ready",
                "method": "ai",
                "provider": "cloudflare_workers_ai",
                "analysis": cached_analysis,
                "is_generative_ai": True,
                "canvas_size": [target_w, target_h],
                "placed_box": [ox, oy, ox + pw, oy + ph],
                "product_preserved": True,
                "foreground_mode": foreground_mode,
                "foreground_fidelity": "pixel_identical" if foreground_mode == "original" else "ai_enhanced_detail",
                "foreground_status": "original_approved" if foreground_mode == "original" else "realesrgan_enhanced",
                "foreground_description": (
                    "Original customer-approved pixels preserved without alteration."
                    if foreground_mode == "original"
                    else "Real-ESRGAN CNN super-resolution enhanced foreground for improved apparent detail. Not claimed to be pixel-identical to source."
                ),
                "error_message": None,
            }
        else:
            logger.warning(f"Cloudflare inpainting failed for ({target_w}x{target_h}): {cf_err}")
    else:
        cf_err = "Cloudflare credentials not configured"

    # 2. Honest Fallback: if AI generation failed or credentials absent
    if allow_opencv_fallback:
        fallback_img = studio_texture_background_expansion(
            img_rgb=img,
            target_w=target_w,
            target_h=target_h,
            placed_w=pw,
            placed_h=ph,
            offset_x=ox,
            offset_y=oy,
            expansion_type=ext_type,
            bg_color_hex=bg_color_hex,
            is_transparent=is_transparent,
            vision_info=cached_analysis,
            foreground_img=foreground_img,
        )
        return fallback_img, {
            "status": "fallback",
            "method": "ai",
            "provider": "studio_fallback",
            "analysis": cached_analysis,
            "is_generative_ai": False,
            "canvas_size": [target_w, target_h],
            "placed_box": [ox, oy, ox + pw, oy + ph],
            "product_preserved": True,
            "foreground_mode": foreground_mode,
            "foreground_fidelity": "pixel_identical" if foreground_mode == "original" else "ai_enhanced_detail",
            "foreground_status": "original_approved" if foreground_mode == "original" else "realesrgan_enhanced",
            "foreground_description": (
                "Original customer-approved pixels preserved without alteration."
                if foreground_mode == "original"
                else "Real-ESRGAN CNN super-resolution enhanced foreground for improved apparent detail. Not claimed to be pixel-identical to source."
            ),
            "error_message": f"AI generation unavailable ({cf_err}). Displaying adaptive fallback.",
        }

    # 3. Explicit Failure if fallback not allowed
    return None, {
        "status": "failed",
        "method": "ai",
        "provider": "none",
        "is_generative_ai": False,
        "canvas_size": [target_w, target_h],
        "placed_box": [ox, oy, ox + pw, oy + ph],
        "product_preserved": False,
        "error_message": cf_err or "AI background generation failed.",
    }


def expand_background_ai(
    img: Image.Image,
    target_w: int,
    target_h: int,
    prompt_hint: Optional[str] = None,
    bg_color_hex: str = "#F8FAFC",
    allow_opencv_fallback: bool = True,
    subject_bbox: Optional[Any] = None,
    is_transparent: bool = False,
    cached_analysis: Optional[Any] = None,
    **kwargs
) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
    """Method B main expansion interface."""
    return expand_background_groq(
        img=img,
        target_w=target_w,
        target_h=target_h,
        prompt_hint=prompt_hint,
        cached_analysis=cached_analysis,
        bg_color_hex=bg_color_hex,
        is_transparent=is_transparent,
        allow_opencv_fallback=allow_opencv_fallback,
        **kwargs
    )


# Backwards-compatible aliases
expand_background_product_safe = expand_background_ai
