"""Crop and aspect ratio transformation engine for Ratio Studio.
Professional full-frame Smart Crop (default) and Safe Fit (clean solid studio background).
No blurred duplicate image effects.
"""

from typing import Dict, Any, Tuple, Optional, List
import numpy as np
import cv2
from PIL import Image

# Predefined standard ratio specs with descriptive safe keys and legacy aliases
RATIO_CONFIGS: Dict[str, Dict[str, Any]] = {
    "1:1": {
        "name": "Square (1:1)",
        "ratio_key": "1:1",
        "safe_key": "square_1x1",
        "legacy_key": "1x1",
        "aliases": ["1x1", "square_1x1", "1:1", "square"],
        "width": 2048,
        "height": 2048,
        "orientation": "Square",
        "aspect_w": 1,
        "aspect_h": 1,
    },
    "4:5": {
        "name": "Portrait (4:5)",
        "ratio_key": "4:5",
        "safe_key": "portrait_4x5",
        "legacy_key": "4x5",
        "aliases": ["4x5", "portrait_4x5", "4:5"],
        "width": 1600,
        "height": 2000,
        "orientation": "Portrait",
        "aspect_w": 4,
        "aspect_h": 5,
    },
    "3:4": {
        "name": "Portrait (3:4)",
        "ratio_key": "3:4",
        "safe_key": "portrait_3x4",
        "legacy_key": "3x4",
        "aliases": ["3x4", "portrait_3x4", "3:4"],
        "width": 1536,
        "height": 2048,
        "orientation": "Portrait",
        "aspect_w": 3,
        "aspect_h": 4,
    },
    "16:9": {
        "name": "Landscape (16:9)",
        "ratio_key": "16:9",
        "safe_key": "landscape_16x9",
        "legacy_key": "16x9",
        "aliases": ["16x9", "landscape_16x9", "16:9"],
        "width": 2560,
        "height": 1440,
        "orientation": "Landscape",
        "aspect_w": 16,
        "aspect_h": 9,
    },
    "5:4": {
        "name": "Landscape (5:4)",
        "ratio_key": "5:4",
        "safe_key": "landscape_5x4",
        "legacy_key": "5x4",
        "aliases": ["5x4", "landscape_5x4", "5:4"],
        "width": 2000,
        "height": 1600,
        "orientation": "Landscape",
        "aspect_w": 5,
        "aspect_h": 4,
    },
}


def resolve_ratio_config(key: str) -> Optional[Dict[str, Any]]:
    """Resolve a ratio string (key, safe_key, or alias) to its configuration."""
    normalized = key.strip().lower().replace(":", "x")
    for r_k, config in RATIO_CONFIGS.items():
        if (
            normalized == r_k
            or normalized == config["safe_key"]
            or normalized == config["legacy_key"]
            or normalized in [a.replace(":", "x") for a in config["aliases"]]
        ):
            return config
    return None


def compute_spectral_residual_saliency(img_cv: np.ndarray) -> np.ndarray:
    """
    Classical Spectral Residual Saliency (Hou & Zhang, 2007) combined with edge gradient energy.
    100% traditional mathematics and digital signal processing.
    """
    try:
        calc_size = 160
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
        resized = cv2.resize(gray, (calc_size, calc_size), interpolation=cv2.INTER_AREA)

        # 1. 2D Discrete Fourier Transform Spectral Residual
        dft = cv2.dft(np.float32(resized), flags=cv2.DFT_COMPLEX_OUTPUT)
        magnitude, phase = cv2.cartToPolar(dft[:, :, 0], dft[:, :, 1])
        log_mag = np.log(magnitude + 1e-5)
        avg_log = cv2.boxFilter(log_mag, -1, (3, 3))
        spectral_residual = log_mag - avg_log
        re_x, re_y = cv2.polarToCart(np.exp(spectral_residual), phase)
        inv_dft = cv2.idft(cv2.merge([re_x, re_y]))
        sal_spectral = cv2.magnitude(inv_dft[:, :, 0], inv_dft[:, :, 1]) ** 2
        sal_spectral = cv2.GaussianBlur(sal_spectral, (9, 9), 2.5)

        # 2. Edge / Gradient Energy (Sobel) to strongly detect product/car outlines
        grad_x = cv2.Sobel(resized, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(resized, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = cv2.magnitude(grad_x, grad_y)
        grad_mag = cv2.GaussianBlur(grad_mag, (9, 9), 2.0)

        # Normalize components
        def norm(arr):
            mn, mx = np.min(arr), np.max(arr)
            return (arr - mn) / (mx - mn + 1e-5)

        combined = 0.6 * norm(sal_spectral) + 0.4 * norm(grad_mag)
        combined = norm(combined)

        h, w = img_cv.shape[:2]
        return cv2.resize(combined, (w, h), interpolation=cv2.INTER_LINEAR)
    except Exception:
        h, w = img_cv.shape[:2]
        return np.zeros((h, w), dtype=np.float32)


def detect_saliency_center(img_cv: np.ndarray) -> Tuple[float, float]:
    """
    Detect the visual center of the main subject (x_norm, y_norm in [0, 1]).
    Falls back to center (0.5, 0.5) if inconclusive.
    """
    h, w = img_cv.shape[:2]
    saliency_map = compute_spectral_residual_saliency(img_cv)

    # Threshold low-energy background noise (keep top 40% salient regions)
    threshold = np.percentile(saliency_map, 60)
    filtered = np.where(saliency_map >= threshold, saliency_map, 0.0)

    total_mass = np.sum(filtered)
    if total_mass > 1.0:
        y_indices, x_indices = np.indices(filtered.shape)
        center_x = np.sum(x_indices * filtered) / total_mass
        center_y = np.sum(y_indices * filtered) / total_mass
        # Gentle dampening towards center to avoid extreme cutoffs
        cx_norm = 0.15 * 0.5 + 0.85 * (center_x / w)
        cy_norm = 0.15 * 0.5 + 0.85 * (center_y / h)
        return float(np.clip(cx_norm, 0.1, 0.9)), float(np.clip(cy_norm, 0.1, 0.9))

    return 0.5, 0.5


def calculate_crop_window(
    orig_w: int,
    orig_h: int,
    target_ratio: float,
    center_x_norm: float = 0.5,
    center_y_norm: float = 0.5
) -> Tuple[int, int, int, int]:
    """
    Calculate bounding box (left, top, right, bottom) of maximum size
    with given target_ratio, centered around (center_x_norm, center_y_norm).
    Strictly contained within original image. Never stretches.
    """
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        # Source image is wider than target ratio: full height, crop width
        crop_h = orig_h
        crop_w = int(round(orig_h * target_ratio))
        crop_w = min(crop_w, orig_w)
    else:
        # Source image is taller than target ratio: full width, crop height
        crop_w = orig_w
        crop_h = int(round(orig_w / target_ratio))
        crop_h = min(crop_h, orig_h)

    desired_cx = center_x_norm * orig_w
    desired_cy = center_y_norm * orig_h

    left = int(round(desired_cx - (crop_w / 2.0)))
    top = int(round(desired_cy - (crop_h / 2.0)))

    left = max(0, min(left, orig_w - crop_w))
    top = max(0, min(top, orig_h - crop_h))
    right = left + crop_w
    bottom = top + crop_h

    return left, top, right, bottom


def process_safe_fit(
    img: Image.Image,
    target_w: int,
    target_h: int,
    bg_color_hex: str = "#18181B",
    is_transparent: bool = False
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """
    Safe Fit Mode:
    - Preserves 100% of the original image without any cropping.
    - Proportionally scales foreground using LANCZOS.
    - Clean solid background (no blurred duplicate effect, no picture-in-picture).
    - Perfect for when user wants zero content trimmed.
    """
    orig_w, orig_h = img.size
    scale = min(target_w / orig_w, target_h / orig_h)
    fit_w = max(1, int(round(orig_w * scale)))
    fit_h = max(1, int(round(orig_h * scale)))

    foreground = img.resize((fit_w, fit_h), resample=Image.Resampling.LANCZOS)

    if is_transparent:
        canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    else:
        bg_hex = bg_color_hex.lstrip("#")
        if len(bg_hex) == 6:
            bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
        else:
            bg_rgb = (24, 24, 27)

        canvas_mode = "RGBA" if img.mode == "RGBA" else "RGB"
        color_fill = (*bg_rgb, 255) if canvas_mode == "RGBA" else bg_rgb
        canvas = Image.new(canvas_mode, (target_w, target_h), color_fill)

    paste_x = (target_w - fit_w) // 2
    paste_y = (target_h - fit_h) // 2

    if foreground.mode == "RGBA":
        canvas.paste(foreground, (paste_x, paste_y), mask=foreground.split()[-1])
    else:
        canvas.paste(foreground, (paste_x, paste_y))

    return canvas, (0, 0, orig_w, orig_h)


def process_image_for_ratio(
    img: Image.Image,
    target_config: Dict[str, Any],
    mode: str = "smart_crop",
    bg_color_hex: str = "#18181B",
    is_transparent: bool = False,
    manual_crop: Optional[Tuple[int, int, int, int]] = None
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """
    Process image according to specified mode and ratio config.
    Default mode: 'smart_crop' (Professional full-frame crop, subject-centered, no blur).
    Alternative mode: 'safe_fit' (Preserves full image with clean solid background).
    Output dimensions are guaranteed to match target_config width and height exactly.
    """
    target_w = target_config["width"]
    target_h = target_config["height"]
    target_ratio = target_w / target_h
    orig_w, orig_h = img.size

    # 1. Manual Crop
    if manual_crop is not None:
        left, top, right, bottom = manual_crop
        left = max(0, min(left, orig_w - 1))
        top = max(0, min(top, orig_h - 1))
        right = max(left + 1, min(right, orig_w))
        bottom = max(top + 1, min(bottom, orig_h))
        crop_box = (left, top, right, bottom)

        cropped = img.crop(crop_box)
        result = cropped.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
        return result, crop_box

    # 2. Safe Fit (Alternative: full image preserved on clean solid background)
    if mode in ["safe_fit", "fit_contain", "smart_fit"]:
        return process_safe_fit(
            img=img,
            target_w=target_w,
            target_h=target_h,
            bg_color_hex=bg_color_hex,
            is_transparent=is_transparent
        )

    # 3. Professional Smart Crop (Default: full-frame, subject-prominent, no blur)
    try:
        cv_img = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
        center_x, center_y = detect_saliency_center(cv_img)
    except Exception:
        center_x, center_y = 0.5, 0.5

    crop_box = calculate_crop_window(orig_w, orig_h, target_ratio, center_x, center_y)
    cropped = img.crop(crop_box)
    result = cropped.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
    return result, crop_box
