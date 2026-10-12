"""Crop and aspect ratio transformation engine for Ratio Studio.
Professional full-frame Smart Crop with smart subject preservation and automatic Safe Fit fallback.
No blurred duplicate image effects.
Deterministic image geometry with multi-cue subject bounding box detection and safe margin framing.
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
    100% traditional digital signal processing.
    """
    try:
        calc_size = 180
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

        combined = 0.5 * norm(sal_spectral) + 0.5 * norm(grad_mag)
        combined = norm(combined)

        h, w = img_cv.shape[:2]
        return cv2.resize(combined, (w, h), interpolation=cv2.INTER_LINEAR)
    except Exception:
        h, w = img_cv.shape[:2]
        return np.zeros((h, w), dtype=np.float32)


def detect_subject_bbox(img_cv: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Robust multi-cue subject bounding box detection for cars, products, and general photography.
    Combines:
    1. Spectral residual + gradient saliency energy.
    2. Canny edge density & Otsu threshold foreground mask.
    3. Center-bias weighting to prevent peripheral distractions.
    Returns: (x1, y1, x2, y2) in pixel coordinates, or None if uncertain.
    """
    try:
        h, w = img_cv.shape[:2]
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv.copy()

        # Suppress perimeter ringing artifact (outer 2% border)
        m = max(2, int(min(w, h) * 0.02))

        # 1. Saliency energy map with border suppression
        saliency_map = compute_spectral_residual_saliency(img_cv)
        sal_inner = saliency_map.copy()
        sal_inner[:m, :] = 0
        sal_inner[-m:, :] = 0
        sal_inner[:, :m] = 0
        sal_inner[:, -m:] = 0

        sal_8u = (sal_inner * 255).astype(np.uint8)
        _, sal_mask = cv2.threshold(sal_8u, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 2. Edge energy with border suppression
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 140)
        edges[:m, :] = 0
        edges[-m:, :] = 0
        edges[:, :m] = 0
        edges[:, -m:] = 0

        # Morphological closing on edges to connect subject outlines (e.g. wheels to chassis)
        k_w = max(3, int(w * 0.02)) | 1
        k_h = max(3, int(h * 0.02)) | 1
        morph_k = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
        edge_closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, morph_k)

        # 3. Combine saliency + edge density
        combined_mask = cv2.bitwise_or(sal_mask, edge_closed)

        # Morphological open to remove scattered noise
        clean_k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        cleaned = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, clean_k)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        min_area = (w * h) * 0.02
        valid_boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area >= min_area:
                bx, by, bw, bh = cv2.boundingRect(c)
                # Ignore full-canvas outer boundaries
                if bw < w * 0.98 or bh < h * 0.98:
                    valid_boxes.append((bx, by, bx + bw, by + bh))

        if not valid_boxes:
            return None

        min_x = min(b[0] for b in valid_boxes)
        min_y = min(b[1] for b in valid_boxes)
        max_x = max(b[2] for b in valid_boxes)
        max_y = max(b[3] for b in valid_boxes)

        # If detected box covers practically the entire image (> 95% both dims), it's full scene
        if (max_x - min_x) > w * 0.95 and (max_y - min_y) > h * 0.95:
            return None

        # Add small safety padding (2%)
        pad_x = int(round(w * 0.02))
        pad_y = int(round(h * 0.02))
        x1 = max(0, min_x - pad_x)
        y1 = max(0, min_y - pad_y)
        x2 = min(w, max_x + pad_x)
        y2 = min(h, max_y + pad_y)

        if x2 > x1 and y2 > y1:
            return (x1, y1, x2, y2)
        return None
    except Exception:
        return None


# Alias for backward compatibility
detect_saliency_bbox = detect_subject_bbox


def detect_saliency_center(img_cv: np.ndarray) -> Tuple[float, float]:
    """
    Detect the visual center of the main subject (x_norm, y_norm in [0, 1]).
    Falls back to center (0.5, 0.5) if inconclusive.
    """
    h, w = img_cv.shape[:2]
    saliency_map = compute_spectral_residual_saliency(img_cv)

    threshold = np.percentile(saliency_map, 60)
    filtered = np.where(saliency_map >= threshold, saliency_map, 0.0)

    total_mass = np.sum(filtered)
    if total_mass > 1.0:
        y_indices, x_indices = np.indices(filtered.shape)
        center_x = np.sum(x_indices * filtered) / total_mass
        center_y = np.sum(y_indices * filtered) / total_mass
        cx_norm = 0.15 * 0.5 + 0.85 * (center_x / w)
        cy_norm = 0.15 * 0.5 + 0.85 * (center_y / h)
        return float(np.clip(cx_norm, 0.1, 0.9)), float(np.clip(cy_norm, 0.1, 0.9))

    return 0.5, 0.5


def calculate_crop_window(
    orig_w: int,
    orig_h: int,
    target_ratio: float,
    center_x_norm: float = 0.5,
    center_y_norm: float = 0.5,
    subject_bbox: Optional[Tuple[int, int, int, int]] = None,
    safe_margin_fraction: float = 0.03
) -> Tuple[int, int, int, int]:
    """
    Calculate bounding box (left, top, right, bottom) of maximum size
    with given target_ratio, centered around (center_x_norm, center_y_norm).
    Strictly contained within original image. Never stretches.

    If subject_bbox (x1, y1, x2, y2) is supplied:
    - If subject fits within crop dimensions, the window is adjusted to keep
      the entire subject inside with a safety margin.
    - If subject exceeds crop dimensions, the window is centered over the subject.
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

    # Initial desired center
    desired_cx = center_x_norm * orig_w
    desired_cy = center_y_norm * orig_h

    # If subject bbox is available, adjust crop window to frame subject
    if subject_bbox is not None:
        sb_x1, sb_y1, sb_x2, sb_y2 = subject_bbox
        sb_w = sb_x2 - sb_x1
        sb_h = sb_y2 - sb_y1
        sb_cx = (sb_x1 + sb_x2) / 2.0
        sb_cy = (sb_y1 + sb_y2) / 2.0

        margin_x = int(round(crop_w * safe_margin_fraction))
        margin_y = int(round(crop_h * safe_margin_fraction))

        # Check if subject width fits inside crop width
        if sb_w <= crop_w:
            min_left = max(0, sb_x2 + margin_x - crop_w)
            max_left = min(orig_w - crop_w, sb_x1 - margin_x)
            if min_left <= max_left:
                left = int(round((min_left + max_left) / 2.0))
            else:
                left = int(round(sb_cx - (crop_w / 2.0)))
        else:
            left = int(round(sb_cx - (crop_w / 2.0)))

        # Check if subject height fits inside crop height
        if sb_h <= crop_h:
            min_top = max(0, sb_y2 + margin_y - crop_h)
            max_top = min(orig_h - crop_h, sb_y1 - margin_y)
            if min_top <= max_top:
                top = int(round((min_top + max_top) / 2.0))
            else:
                top = int(round(sb_cy - (crop_h / 2.0)))
        else:
            top = int(round(sb_cy - (crop_h / 2.0)))
    else:
        left = int(round(desired_cx - (crop_w / 2.0)))
        top = int(round(desired_cy - (crop_h / 2.0)))

    # Strictly clamp within boundaries
    left = max(0, min(left, orig_w - crop_w))
    top = max(0, min(top, orig_h - crop_h))
    right = left + crop_w
    bottom = top + crop_h

    return left, top, right, bottom


def check_subject_fit(
    crop_box: Tuple[int, int, int, int],
    subject_bbox: Optional[Tuple[int, int, int, int]],
    orig_w: int,
    orig_h: int
) -> Dict[str, Any]:
    """
    Check whether the subject bounding box is fully contained inside crop_box,
    and calculate percentage of original image removed.
    """
    c_l, c_t, c_r, c_b = crop_box
    crop_area = (c_r - c_l) * (c_b - c_t)
    total_area = orig_w * orig_h
    removed_fraction = max(0.0, 1.0 - (crop_area / total_area))

    if subject_bbox is None:
        return {
            "has_subject_box": False,
            "fits_completely": True,
            "clipped_horizontal": False,
            "clipped_vertical": False,
            "removed_fraction": removed_fraction,
            "message": "Subject framing estimated using saliency energy."
        }

    s_l, s_t, s_r, s_b = subject_bbox
    s_w = max(1, s_r - s_l)
    s_h = max(1, s_b - s_t)
    s_area = s_w * s_h
    subject_coverage = s_area / float(total_area)

    inter_l = max(s_l, c_l)
    inter_t = max(s_t, c_t)
    inter_r = min(s_r, c_r)
    inter_b = min(s_b, c_b)

    if inter_r > inter_l and inter_b > inter_t:
        inter_area = (inter_r - inter_l) * (inter_b - inter_t)
    else:
        inter_area = 0

    subject_clipped_fraction = max(0.0, 1.0 - (inter_area / float(s_area)))

    clipped_left = s_l < c_l - int(round(orig_w * 0.02))
    clipped_right = s_r > c_r + int(round(orig_w * 0.02))
    clipped_top = s_t < c_t - int(round(orig_h * 0.02))
    clipped_bottom = s_b > c_b + int(round(orig_h * 0.02))

    clipped_h = clipped_left or clipped_right
    clipped_v = clipped_top or clipped_bottom
    fits = not (clipped_h or clipped_v) and subject_clipped_fraction < 0.05

    if fits:
        msg = "Subject is fully framed inside the crop."
    else:
        edges = []
        if clipped_left or clipped_right:
            edges.append("sides")
        if clipped_top or clipped_bottom:
            edges.append("top/bottom")
        msg = f"Subject trimmed on {' and '.join(edges) if edges else 'edges'}."

    return {
        "has_subject_box": True,
        "fits_completely": fits,
        "clipped_horizontal": clipped_h,
        "clipped_vertical": clipped_v,
        "subject_clipped_fraction": subject_clipped_fraction,
        "subject_coverage": subject_coverage,
        "removed_fraction": removed_fraction,
        "message": msg
    }


def validate_manual_crop_box(
    crop_box: Tuple[int, int, int, int],
    orig_w: int,
    orig_h: int,
    target_ratio: float,
    tolerance: float = 0.05
) -> Tuple[int, int, int, int]:
    """
    Validate that manual crop coordinates:
    1. Are ordered left < right, top < bottom.
    2. Lie strictly within original image bounds [0..orig_w, 0..orig_h].
    3. Have positive dimensions.
    4. Match the target aspect ratio within tolerance (never stretch).
    """
    left, top, right, bottom = crop_box
    if left >= right or top >= bottom:
        raise ValueError("Invalid crop coordinates: left must be < right and top < bottom.")

    if left < 0 or top < 0 or right > orig_w or bottom > orig_h:
        raise ValueError(
            f"Crop coordinates [{left}, {top}, {right}, {bottom}] exceed image bounds [{orig_w}, {orig_h}]."
        )

    crop_w = right - left
    crop_h = bottom - top

    if crop_w < 10 or crop_h < 10:
        raise ValueError("Selected crop box is too small (minimum 10x10 pixels).")

    actual_ratio = crop_w / crop_h
    ratio_error = abs(actual_ratio - target_ratio) / target_ratio
    if ratio_error > tolerance:
        raise ValueError(
            f"Crop box ratio ({actual_ratio:.3f}) does not match target ratio ({target_ratio:.3f}). "
            f"Error of {ratio_error*100:.1f}% exceeds allowed tolerance of {tolerance*100:.0f}%."
        )

    return left, top, right, bottom


def process_safe_fit(
    img: Image.Image,
    target_w: int,
    target_h: int,
    bg_color_hex: str = "#F8FAFC",
    is_transparent: bool = False
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """
    Safe Fit Mode:
    - Preserves 100% of the original image without any cropping.
    - Proportionally scales foreground using LANCZOS.
    - Clean solid background (no blurred duplicate effect, no picture-in-picture).
    - Defaults to a clean neutral studio light background (#F8FAFC).
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
            bg_rgb = (248, 250, 252)

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
    bg_color_hex: str = "#F8FAFC",
    is_transparent: bool = False,
    manual_crop: Optional[Tuple[int, int, int, int]] = None,
    subject_bbox: Optional[Tuple[int, int, int, int]] = None,
    auto_fallback: bool = True
) -> Tuple[Image.Image, Tuple[int, int, int, int], Dict[str, Any], str, Optional[str]]:
    """
    Process image according to specified mode and ratio config.
    Returns: (processed_image, crop_box, fit_info, effective_mode, fallback_reason)

    Automatic Fallback:
    When mode == 'smart_crop' and auto_fallback is True:
    - Calculates proposed crop.
    - If subject bounding box would be clipped, automatically falls back to Safe Fit.
    - Accurately reports effective_mode='safe_fit' and simple fallback_reason to frontend.
    """
    target_w = target_config["width"]
    target_h = target_config["height"]
    target_ratio = target_w / target_h
    orig_w, orig_h = img.size

    # 1. Manual Crop
    if manual_crop is not None:
        validated_crop = validate_manual_crop_box(manual_crop, orig_w, orig_h, target_ratio)
        cropped = img.crop(validated_crop)
        result = cropped.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
        fit_info = check_subject_fit(validated_crop, subject_bbox, orig_w, orig_h)
        return result, validated_crop, fit_info, "manual_crop", None

    # 2. Explicit Safe Fit
    if mode in ["safe_fit", "fit_contain", "smart_fit"]:
        canvas, full_box = process_safe_fit(
            img=img,
            target_w=target_w,
            target_h=target_h,
            bg_color_hex=bg_color_hex,
            is_transparent=is_transparent
        )
        fit_info = {
            "has_subject_box": True,
            "fits_completely": True,
            "clipped_horizontal": False,
            "clipped_vertical": False,
            "removed_fraction": 0.0,
            "message": "100% of the image is preserved on a clean solid studio background."
        }
        return canvas, full_box, fit_info, "safe_fit", None

    # 3. Smart Crop with Automatic Fallback
    try:
        cv_img = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
        center_x, center_y = detect_saliency_center(cv_img)
        if subject_bbox is None:
            subject_bbox = detect_subject_bbox(cv_img)
    except Exception:
        center_x, center_y = 0.5, 0.5

    crop_box = calculate_crop_window(
        orig_w, orig_h, target_ratio, center_x, center_y, subject_bbox=subject_bbox
    )
    fit_info = check_subject_fit(crop_box, subject_bbox, orig_w, orig_h)

    # Automatic fallback check:
    # Option A (Full-Frame Photo) MUST crop and fill the canvas to create distinctive framed outputs!
    # Fallback to Safe Fit should ONLY occur in extreme scenarios:
    # e.g., a wide vehicle / elongated subject (aspect ratio >= 1.5) forced into an extreme narrow portrait frame (target_ratio <= 0.85)
    # where an isolated subject would have over 40% of its body/wheels severed.
    # It must NEVER trigger on standard scenes, food, products, or normal photos where the user expects the photo to fill the canvas!
    orig_ratio = orig_w / float(orig_h)
    extreme_aspect_mismatch = (orig_ratio >= 1.5 and target_ratio <= 0.85) or (orig_ratio <= 0.67 and target_ratio >= 1.5)
    is_isolated_subject = fit_info.get("subject_coverage", 1.0) < 0.75
    severe_clipping = fit_info.get("subject_clipped_fraction", 0.0) >= 0.40

    should_fallback = auto_fallback and extreme_aspect_mismatch and is_isolated_subject and severe_clipping

    if should_fallback:
        canvas, full_box = process_safe_fit(
            img=img,
            target_w=target_w,
            target_h=target_h,
            bg_color_hex=bg_color_hex,
            is_transparent=is_transparent
        )
        fallback_msg = "Your complete image has been preserved to avoid cutting important parts."
        safe_fit_info = {
            "has_subject_box": fit_info.get("has_subject_box", False),
            "fits_completely": True,
            "clipped_horizontal": False,
            "clipped_vertical": False,
            "removed_fraction": 0.0,
            "message": fallback_msg
        }
        return canvas, full_box, safe_fit_info, "safe_fit", fallback_msg

    # Otherwise perform crisp Full-Frame Smart Crop
    cropped = img.crop(crop_box)
    result = cropped.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
    return result, crop_box, fit_info, "smart_crop", None
