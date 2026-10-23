"""Product-Safe AI & Commercial Studio Background Expansion Service for Ratio Studio.
Maintains 100% pixel fidelity for jewellery, products, vehicles, landscapes, and portraits.

Features:
1. Provider Adapter Architecture:
   - OpenAIOutpaintingProvider: Genuine DALL-E 2 inpainting API with proportional canvas and alpha mask.
   - GeminiOutpaintingProvider: Google GenAI multimodal image generation (paid tier).
   - GroqVisionAdaptiveProvider: Groq Vision (qwen/qwen3.8-27b) scene analysis + atmospheric 2D diffusion fallback.
2. Aspect-Ratio-Preserving Canvas Construction: Exact math for 1:1, 4:5, 3:4, 16:9, 5:4.
3. Strict Subject Protection: Re-composites pristine original fitted pixels over the generated canvas.
4. Transparent Status Attribution:
   - 'ready': Genuine generative AI outpainting succeeded.
   - 'fallback': Classical computer vision fallback used (clearly labeled).
   - 'unavailable': No valid generative AI credentials configured.
   - 'failed': API call encountered an error.
"""

import os
import io
import math
import time
import json
import base64
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, List
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageDraw

# Load environment variables from backend/.env if present
try:
    import dotenv
    dotenv.load_dotenv()
except Exception:
    pass

from services.groq_vision import (
    analyze_scene_for_background_expansion,
    is_groq_enabled,
)


def get_configured_ai_provider() -> str:
    """Check which AI/expansion provider is configured in environment."""
    try:
        import dotenv
        pass
    except Exception:
        pass

    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    return "studio"


def calculate_expansion_canvas(
    orig_w: int,
    orig_h: int,
    target_w: int,
    target_h: int
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
        offset_y = (target_h - placed_h) // 2
        return placed_w, placed_h, offset_x, offset_y, "vertical"


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
    **kwargs
) -> Image.Image:
    """
    High-fidelity background expansion fallback using computer vision:
    1. Studio/Product: For uniform solid backdrops, extends seamless matching studio tone.
    2. Scenery/Photographs: Uses perimeter-isolated 2D multi-scale atmospheric diffusion:
       - Samples exclusively from the outermost perimeter strips (bounded by subject bounding box).
       - Never mirrors central subjects (no duplicated towers, people, vehicles).
       - Uses 2D Gaussian blur + cubic Hermite blending to eliminate barcode scanlines.
       - Adds subtle atmospheric micro-texture to blend naturally with photography.
    3. Re-composites pristine untouched source pixels with anti-aliasing.
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

    canvas_np = np.zeros((target_h, target_w, 3), dtype=np.uint8)

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

    # Handle solid/studio backgrounds
    if custom_bg is not None or scene_type in ["studio_solid", "graphic"] or perim_std < 5.0:
        fill_color = custom_bg if custom_bg is not None else tuple(int(c) for c in perim_median)
        canvas_np[:, :] = fill_color
    else:
        # Determine safe strip bounds using vision subject bounding box
        # subject_box format: [ymin%, xmin%, ymax%, xmax%]
        subj_box = info.get("subject_box") or [10, 10, 90, 90]
        try:
            ymin_pct = subj_box[0] / 100.0 if len(subj_box) >= 4 else 0.15
            xmin_pct = subj_box[1] / 100.0 if len(subj_box) >= 4 else 0.15
            ymax_pct = subj_box[2] / 100.0 if len(subj_box) >= 4 else 0.85
            xmax_pct = subj_box[3] / 100.0 if len(subj_box) >= 4 else 0.85
        except Exception:
            ymin_pct, xmin_pct, ymax_pct, xmax_pct = 0.15, 0.15, 0.85, 0.85

        # Maximum width of edge strip we can sample without touching central subject
        max_left_strip = max(8, min(int(round(placed_w * xmin_pct * 0.7)), placed_w // 10))
        max_right_strip = max(8, min(int(round(placed_w * (1.0 - xmax_pct) * 0.7)), placed_w // 10))
        max_top_strip = max(8, min(int(round(placed_h * ymin_pct * 0.7)), placed_h // 10))
        max_bot_strip = max(8, min(int(round(placed_h * (1.0 - ymax_pct) * 0.7)), placed_h // 10))

        # 1. HORIZONTAL EXTENSION (WINGS)
        if pad_left > 0 or pad_right > 0:
            if pad_left > 0:
                strip_w = max(8, min(36, max_left_strip))
                left_strip = placed_np[:, :strip_w, :]

                # Seamless reflection of ONLY the outermost thin edge background strip
                left_padded = cv2.copyMakeBorder(left_strip, 0, 0, pad_left, 0, cv2.BORDER_REFLECT_101)[:, :pad_left, :]

                # 2D Multi-scale atmospheric diffusion (completely eliminates horizontal barcode stripes)
                kw = max(31, (pad_left // 6) | 1)
                kh = max(31, (target_h // 20) | 1)
                diffused = cv2.GaussianBlur(left_padded, (kw, kh), 0)

                dist_map = np.linspace(1.0, 0.0, pad_left, dtype=np.float32)
                w_blend = (dist_map ** 2 * (3.0 - 2.0 * dist_map))[None, :, None]

                left_wing = (
                    left_padded.astype(np.float32) * (1.0 - w_blend * 0.90) +
                    diffused.astype(np.float32) * (w_blend * 0.90)
                )

                # Micro-texture noise to eliminate flat artificial gradients
                np.random.seed(42)
                noise = np.random.normal(0, 1.2, left_wing.shape).astype(np.float32)
                canvas_np[:, :pad_left] = np.clip(left_wing + noise, 0, 255).astype(np.uint8)

            if pad_right > 0:
                strip_w = max(8, min(36, max_right_strip))
                right_strip = placed_np[:, -strip_w:, :]

                right_padded = cv2.copyMakeBorder(right_strip, 0, 0, 0, pad_right, cv2.BORDER_REFLECT_101)[:, strip_w:strip_w + pad_right, :]

                kw = max(31, (pad_right // 6) | 1)
                kh = max(31, (target_h // 20) | 1)
                diffused = cv2.GaussianBlur(right_padded, (kw, kh), 0)

                dist_map = np.linspace(0.0, 1.0, pad_right, dtype=np.float32)
                w_blend = (dist_map ** 2 * (3.0 - 2.0 * dist_map))[None, :, None]

                right_wing = (
                    right_padded.astype(np.float32) * (1.0 - w_blend * 0.90) +
                    diffused.astype(np.float32) * (w_blend * 0.90)
                )

                np.random.seed(43)
                noise = np.random.normal(0, 1.2, right_wing.shape).astype(np.float32)
                canvas_np[:, target_w - pad_right:] = np.clip(right_wing + noise, 0, 255).astype(np.uint8)

        # 2. VERTICAL EXTENSION (MARGINS)
        if pad_top > 0 or pad_bottom > 0:
            if pad_top > 0:
                strip_h = max(8, min(36, max_top_strip))
                top_strip = placed_np[:strip_h, :, :]

                top_padded = cv2.copyMakeBorder(top_strip, pad_top, 0, 0, 0, cv2.BORDER_REFLECT_101)[:pad_top, :, :]

                kw = max(31, (target_w // 20) | 1)
                kh = max(31, (pad_top // 6) | 1)
                diffused = cv2.GaussianBlur(top_padded, (kw, kh), 0)

                dist_map = np.linspace(1.0, 0.0, pad_top, dtype=np.float32)
                w_blend = (dist_map ** 2 * (3.0 - 2.0 * dist_map))[:, None, None]

                top_wing = (
                    top_padded.astype(np.float32) * (1.0 - w_blend * 0.90) +
                    diffused.astype(np.float32) * (w_blend * 0.90)
                )
                canvas_np[:pad_top, :] = np.clip(top_wing, 0, 255).astype(np.uint8)

            if pad_bottom > 0:
                strip_h = max(8, min(36, max_bot_strip))
                bot_strip = placed_np[-strip_h:, :, :]

                bot_padded = cv2.copyMakeBorder(bot_strip, 0, pad_bottom, 0, 0, cv2.BORDER_REFLECT_101)[strip_h:strip_h + pad_bottom, :, :]

                kw = max(31, (target_w // 20) | 1)
                kh = max(31, (pad_bottom // 6) | 1)
                diffused = cv2.GaussianBlur(bot_padded, (kw, kh), 0)

                dist_map = np.linspace(0.0, 1.0, pad_bottom, dtype=np.float32)
                w_blend = (dist_map ** 2 * (3.0 - 2.0 * dist_map))[:, None, None]

                bot_wing = (
                    bot_padded.astype(np.float32) * (1.0 - w_blend * 0.90) +
                    diffused.astype(np.float32) * (w_blend * 0.90)
                )
                canvas_np[target_h - pad_bottom:, :] = np.clip(bot_wing, 0, 255).astype(np.uint8)

    # 3. COMPOSITE PRISTINE ORIGINAL PIXELS
    canvas_np[offset_y:offset_y + placed_h, offset_x:offset_x + placed_w] = placed_np
    res_img = Image.fromarray(canvas_np)

    # Feather edge border 1px to avoid rasterization gap
    mask_im = Image.new("L", (placed_w, placed_h), 255)
    if placed_w > 8 and placed_h > 8:
        draw = ImageDraw.Draw(mask_im)
        draw.rectangle([0, 0, placed_w - 1, placed_h - 1], outline=215, width=1)

    res_img.paste(placed_img, (offset_x, offset_y), mask=mask_im)
    return res_img


# =========================================================================
# PROVIDER ADAPTER ARCHITECTURE
# =========================================================================

class BaseOutpaintingProvider(ABC):
    """Abstract base class for background outpainting and expansion providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_generative(self) -> bool:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def outpaint(
        self,
        source_img: Image.Image,
        target_w: int,
        target_h: int,
        prompt_hint: Optional[str] = None,
        vision_info: Optional[Dict[str, Any]] = None,
        bg_color_hex: str = "#F8FAFC",
        is_transparent: bool = False,
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        pass


class OpenAIOutpaintingProvider(BaseOutpaintingProvider):
    """
    Genuine AI Outpainting Provider using official OpenAI Images API (DALL-E 2 Inpainting).
    Workflow:
    1. Proportional placement into 1024x1024 canvas fitting target aspect ratio.
    2. Transparent alpha mask on missing expansion areas.
    3. Groq Vision scene-aware prompt integration.
    4. Post-generation crop and strict original pixel compositing.
    """

    @property
    def name(self) -> str:
        return "openai"

    @property
    def is_generative(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def outpaint(
        self,
        source_img: Image.Image,
        target_w: int,
        target_h: int,
        prompt_hint: Optional[str] = None,
        vision_info: Optional[Dict[str, Any]] = None,
        bg_color_hex: str = "#F8FAFC",
        is_transparent: bool = False,
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None, "OpenAI API key not configured."

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=50.0)

            square_size = 1024
            target_ratio = target_w / float(target_h)

            # 1. Determine bounding box matching target ratio inside 1024x1024
            if target_ratio >= 1.0:
                box_w = square_size
                box_h = int(round(square_size / target_ratio))
            else:
                box_h = square_size
                box_w = int(round(square_size * target_ratio))

            box_x = (square_size - box_w) // 2
            box_y = (square_size - box_h) // 2

            # 2. Proportionally place source inside target aspect bounding box
            orig_w, orig_h = source_img.size
            scale = min(box_w / float(orig_w), box_h / float(orig_h))
            placed_w = max(1, int(round(orig_w * scale)))
            placed_h = max(1, int(round(orig_h * scale)))

            placed_x = box_x + (box_w - placed_w) // 2
            placed_y = box_y + (box_h - placed_h) // 2

            placed_src = source_img.resize((placed_w, placed_h), resample=Image.Resampling.LANCZOS).convert("RGBA")

            # 3. Build image canvas:
            # - Outside (box_x, box_y, box_w, box_h) is opaque black (not edited)
            # - Inside box, extension areas are transparent (alpha=0)
            # - Placed source image is opaque
            image_canvas = Image.new("RGBA", (square_size, square_size), (0, 0, 0, 255))
            transparent_box = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
            image_canvas.paste(transparent_box, (box_x, box_y))
            image_canvas.paste(placed_src, (placed_x, placed_y))

            # 4. Build mask canvas:
            # - In DALL-E 2: alpha=0 indicates inpainting area, alpha=255 indicates protected area
            mask_canvas = Image.new("RGBA", (square_size, square_size), (255, 255, 255, 255))
            transparent_mask_box = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
            mask_canvas.paste(transparent_mask_box, (box_x, box_y))
            protected_rect = Image.new("RGBA", (placed_w, placed_h), (255, 255, 255, 255))
            mask_canvas.paste(protected_rect, (placed_x, placed_y))

            img_bytes_io = io.BytesIO()
            image_canvas.save(img_bytes_io, format="PNG")
            img_bytes = img_bytes_io.getvalue()

            mask_bytes_io = io.BytesIO()
            mask_canvas.save(mask_bytes_io, format="PNG")
            mask_bytes = mask_bytes_io.getvalue()

            # Construct scene-aware prompt using Groq Vision analysis if available
            info = vision_info or {}
            subject_desc = info.get("subject_description", "photograph subject")
            scene_type = info.get("scene_type", "photograph")
            extension_advice = info.get("extension_advice", "extend matching background environment naturally")

            edit_prompt = (
                prompt_hint or
                f"Professional seamless commercial photograph outpainting. Intelligently extend the background environment into the outer transparent margins. "
                f"Continuing {scene_type} environment with matching lighting, depth, and colors: {extension_advice}. "
                f"Subject: {subject_desc}. Maintain realistic photographic perspective. No borders, no frames, no duplicated subjects, no watermarks, no text."
            )

            response = client.images.edit(
                image=img_bytes,
                mask=mask_bytes,
                prompt=edit_prompt,
                n=1,
                size="1024x1024"
            )

            if not response.data or not response.data[0].url:
                return None, "OpenAI did not return an image URL."

            image_url = response.data[0].url
            import httpx
            resp = httpx.get(image_url, timeout=35.0)
            if resp.status_code != 200:
                return None, f"Failed to download generated image from OpenAI (HTTP {resp.status_code})."

            generated_square = Image.open(io.BytesIO(resp.content)).convert("RGB")

            # 5. Crop exact target bounding box
            cropped_target = generated_square.crop((box_x, box_y, box_x + box_w, box_y + box_h))

            # 6. Resize to canonical target dimensions
            final_img = cropped_target.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)

            # 7. Strictly re-composite pristine source pixels with anti-aliasing
            final_pw, final_ph, final_ox, final_oy, _ = calculate_expansion_canvas(
                orig_w, orig_h, target_w, target_h
            )
            pristine_placed = source_img.convert("RGB").resize((final_pw, final_ph), resample=Image.Resampling.LANCZOS)
            feather_mask = Image.new("L", (final_pw, final_ph), 255)
            if final_pw > 8 and final_ph > 8:
                draw = ImageDraw.Draw(feather_mask)
                draw.rectangle([0, 0, final_pw - 1, final_ph - 1], outline=215, width=1)

            final_img.paste(pristine_placed, (final_ox, final_oy), mask=feather_mask)
            return final_img, None

        except Exception as e:
            err_msg = str(e)
            if "insufficient_quota" in err_msg or "rate_limit" in err_msg:
                return None, "OpenAI API quota or rate limit exceeded."
            if "invalid_api_key" in err_msg or "401" in err_msg:
                return None, "Invalid OpenAI API key."
            return None, f"OpenAI outpainting error: {err_msg[:120]}"


class GeminiOutpaintingProvider(BaseOutpaintingProvider):
    """
    Gemini GenAI Outpainting Provider using official google-genai SDK.
    Requires a Google AI Studio API key with paid billing enabled for Imagen/Image generation.
    """

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def is_generative(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

    def outpaint(
        self,
        source_img: Image.Image,
        target_w: int,
        target_h: int,
        prompt_hint: Optional[str] = None,
        vision_info: Optional[Dict[str, Any]] = None,
        bg_color_hex: str = "#F8FAFC",
        is_transparent: bool = False,
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None, "Gemini API key not configured."

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            pw, ph, ox, oy, ext_type = calculate_expansion_canvas(
                source_img.width, source_img.height, target_w, target_h
            )

            # Build inpainting canvas
            canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            placed = source_img.resize((pw, ph), resample=Image.Resampling.LANCZOS).convert("RGBA")
            canvas.paste(placed, (ox, oy))

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")

            info = vision_info or {}
            subj_desc = info.get("subject_description", "photograph subject")
            outpaint_prompt = (
                prompt_hint or
                f"Professional background expansion for commercial photography. Outpaint and fill the transparent canvas margins naturally. "
                f"Subject: {subj_desc}. Match existing lighting, depth of field, perspective, and color palette. "
                f"Keep subject unchanged. Output exact high-resolution commercial quality."
            )

            models_to_try = [
                "gemini-2.5-flash-image",
                "gemini-3.1-flash-image",
                "gemini-3-pro-image",
            ]

            gen_img = None
            last_err = None

            for m_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=m_name,
                        contents=[
                            source_img.convert("RGB"),
                            outpaint_prompt,
                        ],
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            temperature=0.2,
                        ),
                    )
                    if response and hasattr(response, "candidates") and response.candidates:
                        cand = response.candidates[0]
                        if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                            for part in cand.content.parts:
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    raw_bytes = inline_data.data
                                    if isinstance(raw_bytes, str):
                                        raw_bytes = base64.b64decode(raw_bytes)
                                    gen_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
                                    break
                    if gen_img is not None:
                        break
                except Exception as model_err:
                    last_err = str(model_err)
                    if "429" in last_err or "RESOURCE_EXHAUSTED" in last_err:
                        return None, "Gemini quota limit exceeded (Free tier request limit 0). Enable billing in Google AI Studio."
                    continue

            if gen_img is None:
                if last_err and ("429" in last_err or "RESOURCE_EXHAUSTED" in last_err):
                    return None, "Gemini quota limit exceeded (Free tier request limit 0). Enable billing in Google AI Studio."
                return None, f"Gemini error: {(last_err or 'No image returned')[:120]}"

            final_img = gen_img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
            pristine_placed = source_img.convert("RGB").resize((pw, ph), resample=Image.Resampling.LANCZOS)
            feather_mask = Image.new("L", (pw, ph), 255)
            if pw > 8 and ph > 8:
                draw = ImageDraw.Draw(feather_mask)
                draw.rectangle([0, 0, pw - 1, ph - 1], outline=215, width=1)
            final_img.paste(pristine_placed, (ox, oy), mask=feather_mask)
            return final_img, None

        except Exception as e:
            return None, f"Gemini error: {str(e)[:120]}"


class GroqVisionAdaptiveProvider(BaseOutpaintingProvider):
    """
    Groq Vision-Assisted Adaptive Expansion Provider.
    Uses Groq Vision (qwen/qwen3.8-27b) for intelligent scene and composition analysis,
    and Python/OpenCV 2D multi-scale atmospheric diffusion for seamless canvas continuation.
    Non-generative: always labeled honestly as fallback.
    """

    @property
    def name(self) -> str:
        return "groq_vision"

    @property
    def is_generative(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return is_groq_enabled()

    def outpaint(
        self,
        source_img: Image.Image,
        target_w: int,
        target_h: int,
        prompt_hint: Optional[str] = None,
        vision_info: Optional[Dict[str, Any]] = None,
        bg_color_hex: str = "#F8FAFC",
        is_transparent: bool = False,
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        try:
            if vision_info is None:
                vision_info = analyze_scene_for_background_expansion(source_img)

            pw, ph, ox, oy, ext_type = calculate_expansion_canvas(
                source_img.width, source_img.height, target_w, target_h
            )

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
            return expanded, None
        except Exception as e:
            return None, f"Adaptive expansion error: {str(e)[:120]}"


class ProviderRegistry:
    """Manages available outpainting and background expansion providers."""

    def __init__(self):
        self._providers: Dict[str, BaseOutpaintingProvider] = {
            "openai": OpenAIOutpaintingProvider(),
            "gemini": GeminiOutpaintingProvider(),
            "groq_vision": GroqVisionAdaptiveProvider(),
        }

    def get_provider(self, name: Optional[str] = None) -> Optional[BaseOutpaintingProvider]:
        if name and name in self._providers:
            return self._providers[name]
        # Priority: OpenAI -> Gemini -> GroqVision
        for key in ["openai", "gemini", "groq_vision"]:
            provider = self._providers[key]
            if provider.is_configured():
                return provider
        return None


_REGISTRY = ProviderRegistry()


# =========================================================================
# PUBLIC SERVICE INTERFACES
# =========================================================================

def call_groq_vision_guided_expansion(
    source_img: Image.Image,
    target_w: int,
    target_h: int,
    prompt: Optional[str] = None,
    vision_info: Optional[Dict[str, Any]] = None,
    bg_color_hex: str = "#F8FAFC",
    is_transparent: bool = False,
) -> Tuple[Optional[Image.Image], Optional[Dict[str, Any]], Optional[str]]:
    """Legacy helper executing Groq Vision analysis and studio adaptive expansion."""
    if vision_info is None:
        vision_info = analyze_scene_for_background_expansion(source_img)
    provider = GroqVisionAdaptiveProvider()
    img, err = provider.outpaint(
        source_img=source_img,
        target_w=target_w,
        target_h=target_h,
        prompt_hint=prompt,
        vision_info=vision_info,
        bg_color_hex=bg_color_hex,
        is_transparent=is_transparent,
    )
    return img, vision_info, err


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
    preferred_provider: Optional[str] = None,
    **kwargs
) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
    """
    Unified Method B Background Outpainting Pipeline:
    1. Direct Fit: If aspect ratio matches target within 1%, resizes cleanly.
    2. Genuine Generative AI: Attempts OpenAI (or Gemini) outpainting when configured.
    3. Transparent Fallback: If AI is unconfigured or fails, uses Groq Vision-assisted adaptive expansion if allowed.
    4. Strict Attribution: Reports 'ready' with is_generative_ai=True for genuine AI,
       or 'fallback' with is_generative_ai=False for classical computer vision fallback.
    """
    orig_w, orig_h = img.size
    pw, ph, ox, oy, ext_type = calculate_expansion_canvas(orig_w, orig_h, target_w, target_h)

    # 1. Direct Fit check
    if ext_type == "none":
        resized = img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
        return resized, {
            "status": "ready",
            "method": "ai",
            "provider": "direct_fit",
            "is_generative_ai": False,
            "canvas_size": [target_w, target_h],
            "placed_box": [0, 0, target_w, target_h],
            "product_preserved": True,
            "error_message": None,
        }

    # Pre-analyze scene composition with Groq Vision if available
    vision_info = cached_analysis
    if vision_info is None:
        vision_info = analyze_scene_for_background_expansion(img)

    # 2. Try genuine generative AI provider first
    gen_provider_name = preferred_provider or get_configured_ai_provider()
    gen_result: Optional[Image.Image] = None
    gen_err: Optional[str] = None

    if gen_provider_name in ["openai", "gemini"]:
        provider_obj = _REGISTRY.get_provider(gen_provider_name)
        if provider_obj and provider_obj.is_configured():
            gen_result, gen_err = provider_obj.outpaint(
                source_img=img,
                target_w=target_w,
                target_h=target_h,
                prompt_hint=prompt_hint,
                vision_info=vision_info,
                bg_color_hex=bg_color_hex,
                is_transparent=is_transparent,
            )

    # If genuine AI succeeded
    if gen_result is not None:
        return gen_result, {
            "status": "ready",
            "method": "ai",
            "provider": gen_provider_name,
            "is_generative_ai": True,
            "canvas_size": [target_w, target_h],
            "placed_box": [ox, oy, ox + pw, oy + ph],
            "product_preserved": True,
            "error_message": None,
            "vision_info": vision_info,
        }

    # 3. Honest fallback if permitted
    # If caller explicitly disallowed fallback (allow_opencv_fallback=False), respect it.
    fallback_enabled = allow_opencv_fallback and (os.environ.get("ALLOW_OPENCV_FALLBACK", "true").lower() == "true")
    if fallback_enabled:
        adaptive_provider = GroqVisionAdaptiveProvider()
        fallback_img, adaptive_err = adaptive_provider.outpaint(
            source_img=img,
            target_w=target_w,
            target_h=target_h,
            prompt_hint=prompt_hint,
            vision_info=vision_info,
            bg_color_hex=bg_color_hex,
            is_transparent=is_transparent,
        )

        if fallback_img is not None:
            source_type = (vision_info or {}).get("analysis_source", "local_heuristic")
            is_groq = (source_type == "groq_vision")
            return fallback_img, {
                "status": "fallback",
                "method": "ai",
                "provider": "groq_vision" if is_groq else "studio_fallback",
                "is_generative_ai": False,
                "canvas_size": [target_w, target_h],
                "placed_box": [ox, oy, ox + pw, oy + ph],
                "product_preserved": True,
                "error_message": gen_err or ("Generated using Studio adaptive background extension." if not is_groq else "Generated using Groq Vision-assisted background extension."),
                "vision_info": vision_info,
            }

    # 4. Explicit failure / unavailable
    if not gen_err and gen_provider_name not in ["openai", "gemini"]:
        return None, {
            "status": "unavailable",
            "method": "ai",
            "provider": None,
            "is_generative_ai": False,
            "canvas_size": [target_w, target_h],
            "placed_box": [ox, oy, ox + pw, oy + ph],
            "product_preserved": True,
            "error_message": "Generative AI outpainting not configured. Configure OPENAI_API_KEY in backend/.env.",
        }

    return None, {
        "status": "failed",
        "method": "ai",
        "provider": gen_provider_name,
        "is_generative_ai": False,
        "canvas_size": [target_w, target_h],
        "placed_box": [ox, oy, ox + pw, oy + ph],
        "product_preserved": False,
        "error_message": gen_err or "AI generation failed.",
    }


# Backwards-compatible aliases
expand_background_groq = expand_background_ai
expand_background_product_safe = expand_background_ai


def expand_background_gemini(
    img: Image.Image,
    target_w: int,
    target_h: int,
    prompt_hint: Optional[str] = None,
    **kwargs
) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
    """Gemini-specific expansion call."""
    return expand_background_ai(
        img=img,
        target_w=target_w,
        target_h=target_h,
        prompt_hint=prompt_hint,
        preferred_provider="gemini",
        **kwargs
    )
