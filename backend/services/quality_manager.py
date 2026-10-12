"""Image quality and preprocessing utilities for Ratio Studio."""

from typing import Tuple, Optional
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageFilter


def fix_exif_orientation(img: Image.Image) -> Image.Image:
    """
    Correct image orientation using EXIF orientation tag.
    Returns transposed copy or original if no EXIF tag is present.
    """
    try:
        transposed = ImageOps.exif_transpose(img)
        return transposed if transposed is not None else img
    except Exception:
        return img


def ensure_srgb_profile(img: Image.Image) -> Image.Image:
    """
    Ensure the image is in standard sRGB or RGB/RGBA color space.
    Converts CMYK, palette (P), or grayscale (L) to RGB/RGBA.
    """
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        return img.convert("RGBA")
    elif img.mode in ("RGB", "L", "CMYK", "YCbCr", "LAB", "HSV"):
        return img.convert("RGB")
    else:
        return img.convert("RGB")


def handle_alpha_transparency(
    img: Image.Image,
    target_format: str,
    bg_color_hex: str = "#FFFFFF"
) -> Image.Image:
    """
    Handle alpha channel when saving image.
    If target format is JPEG (which doesn't support alpha), composite over
    the specified background color. If PNG or WebP, keep RGBA.
    """
    target_format = target_format.upper()
    if target_format == "JPEG" or target_format == "JPG":
        if img.mode in ("RGBA", "LA"):
            # Parse hex background color
            bg_hex = bg_color_hex.lstrip("#")
            if len(bg_hex) == 6:
                bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
            else:
                bg_rgb = (255, 255, 255)
            
            background = Image.new("RGB", img.size, bg_rgb)
            # Alpha composite
            alpha = img.split()[-1]
            background.paste(img.convert("RGB"), mask=alpha)
            return background
        elif img.mode != "RGB":
            return img.convert("RGB")
    elif target_format in ("PNG", "WEBP"):
        # Keep RGBA or RGB
        if img.mode not in ("RGB", "RGBA"):
            return img.convert("RGBA")
    return img


def apply_mild_sharpening(img: Image.Image) -> Image.Image:
    """
    Apply subtle unsharp mask sharpening to restore high frequencies after resizing.
    Carefully tuned to avoid halos or edge noise.
    """
    # Radius: 1.0, Percent: 35%, Threshold: 3 levels
    return img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=35, threshold=3))


def apply_mild_denoising(img: Image.Image) -> Image.Image:
    """
    Apply mild denoising using OpenCV bilateral filter.
    Bilateral filter preserves sharp edges while smoothing subtle high-frequency noise.
    """
    is_rgba = img.mode == "RGBA"
    rgb_img = img.convert("RGB")
    np_img = np.array(rgb_img)

    # OpenCV uses BGR
    bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
    # Mild bilateral filtering: d=5, sigmaColor=20, sigmaSpace=20
    denoised_bgr = cv2.bilateralFilter(bgr, d=5, sigmaColor=20, sigmaSpace=20)
    denoised_rgb = cv2.cvtColor(denoised_bgr, cv2.COLOR_BGR2RGB)
    result = Image.fromarray(denoised_rgb)

    if is_rgba:
        # Re-attach original alpha channel
        result = result.convert("RGBA")
        result.putalpha(img.split()[-1])
    return result


def validate_aspect_ratio(
    width: int,
    height: int,
    expected_ratio: Tuple[int, int],
    tolerance: float = 0.01
) -> bool:
    """
    Validate that output width and height match the target aspect ratio within tolerance.
    """
    if height == 0:
        return False
    actual_ratio = width / height
    expected = expected_ratio[0] / expected_ratio[1]
    return abs(actual_ratio - expected) <= tolerance
