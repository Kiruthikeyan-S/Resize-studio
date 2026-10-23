import os
import json
import base64
from io import BytesIO
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from PIL import Image

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class SubjectAnalysis(BaseModel):
    category: str = Field(default="general", description="e.g. vehicle, product, portrait, landscape")
    description: str = Field(default="Subject detected", description="Brief description of main subject")
    approximate_center_x: float = Field(default=0.5, ge=0.0, le=1.0)
    approximate_center_y: float = Field(default=0.5, ge=0.0, le=1.0)
    approximate_bbox: Optional[List[float]] = Field(
        default=None, description="[x1_norm, y1_norm, x2_norm, y2_norm] normalized 0..1"
    )
    aspect_sensitivity: str = Field(default="medium", description="low, medium, high")
    recommended_mode: str = Field(default="smart_crop", description="smart_crop or safe_fit")
    risk_notes: Optional[str] = Field(default=None)


def is_groq_enabled() -> bool:
    """Check if Groq library is installed and API key is set in environment."""
    return GROQ_AVAILABLE and bool(os.environ.get("GROQ_API_KEY"))


def analyze_image_with_groq(image_path: str) -> Optional[SubjectAnalysis]:
    """
    Analyze image using Groq Vision API.
    Returns structured SubjectAnalysis or None if unavailable.
    Never raises an uncaught exception to caller.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not GROQ_AVAILABLE or not api_key:
        return None

    if not os.path.exists(image_path):
        return None

    try:
        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            w, h = rgb_img.size
            scale = min(1024 / max(w, h), 1.0)
            if scale < 1.0:
                resized = rgb_img.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)
            else:
                resized = rgb_img

            buffer = BytesIO()
            resized.save(buffer, format="JPEG", quality=85)
            b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")

        client = Groq(api_key=api_key)

        prompt = (
            "Analyze this photograph for professional aspect ratio conversion (e.g. converting to square, portrait 4:5/3:4, landscape 16:9).\n"
            "Respond ONLY with valid JSON conforming to this exact schema:\n"
            "{\n"
            '  "category": "vehicle|product|portrait|landscape|object",\n'
            '  "description": "<brief description of the primary subject>",\n'
            '  "approximate_center_x": <float 0.0 to 1.0>,\n'
            '  "approximate_center_y": <float 0.0 to 1.0>,\n'
            '  "approximate_bbox": [<x1_norm 0..1>, <y1_norm 0..1>, <x2_norm 0..1>, <y2_norm 0..1>],\n'
            '  "aspect_sensitivity": "low|medium|high",\n'
            '  "recommended_mode": "smart_crop|safe_fit",\n'
            '  "risk_notes": "<potential clipping notes for portrait or square crops>"\n'
            "}"
        )

        models_to_try = ["qwen/qwen3.8-27b", "llama-3.2-11b-vision-preview"]
        response = None
        for m_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=m_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                                },
                            ],
                        }
                    ],
                    temperature=0.1,
                    max_tokens=500,
                    response_format={"type": "json_object"},
                )
                if response and response.choices and response.choices[0].message.content:
                    break
            except Exception:
                continue

        if not response or not response.choices or not response.choices[0].message.content:
            return None

        content = response.choices[0].message.content
        parsed = json.loads(content)
        return SubjectAnalysis(**parsed)

    except Exception:
        return None


def analyze_scene_for_background_expansion(img_input) -> Dict[str, Any]:
    """
    Analyze scene composition using Groq Vision API (qwen/qwen3.8-27b).
    Extracts structured editing guidance for background expansion.
    Falls back gracefully to local heuristic analysis on failure.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not GROQ_AVAILABLE or not api_key:
        return _local_scene_heuristic(img_input)

    try:
        if isinstance(img_input, str):
            if not os.path.exists(img_input):
                return _local_scene_heuristic(img_input)
            img = Image.open(img_input).convert("RGB")
        else:
            img = img_input.convert("RGB")

        w, h = img.size
        scale = min(800 / max(w, h), 1.0)
        resized = img.resize((max(32, int(w * scale)), max(32, int(h * scale))), Image.Resampling.LANCZOS)
        buf = BytesIO()
        resized.save(buf, format="JPEG", quality=85)
        b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

        prompt = (
            "You are an expert computer vision and image editing analyst. "
            "Analyze the image and return ONLY a valid JSON object with: "
            "{"
            '"scene_type": "scenery" | "studio_solid" | "studio_gradient" | "portrait" | "product", '
            '"subject_description": "brief description of main subject", '
            '"subject_box": [ymin_percent, xmin_percent, ymax_percent, xmax_percent], '
            '"has_sky": boolean, '
            '"has_ground_or_water": boolean, '
            '"horizon_y_percent": float or null, '
            '"top_color_hex": "#RRGGBB", '
            '"bottom_color_hex": "#RRGGBB", '
            '"left_color_hex": "#RRGGBB", '
            '"right_color_hex": "#RRGGBB", '
            '"dominant_bg_hex": "#RRGGBB", '
            '"extension_advice": "brief background continuation advice"'
            "}"
        )

        client = Groq(api_key=api_key)
        for m_name in ["qwen/qwen3.8-27b", "llama-3.2-11b-vision-preview"]:
            try:
                res = client.chat.completions.create(
                    model=m_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                            ]
                        }
                    ],
                    temperature=0.1,
                    max_tokens=400,
                    response_format={"type": "json_object"}
                )
                raw = res.choices[0].message.content
                if raw:
                    parsed = json.loads(raw)
                    parsed["groq_model"] = m_name
                    parsed["analysis_source"] = "groq_vision"
                    return parsed
            except Exception:
                continue

        return _local_scene_heuristic(img)

    except Exception:
        return _local_scene_heuristic(img_input)


def _local_scene_heuristic(img_input) -> Dict[str, Any]:
    """Offline heuristic scene analysis when Groq is unreachable."""
    try:
        import numpy as np
        if isinstance(img_input, str):
            if not os.path.exists(img_input):
                return {"scene_type": "scenery", "analysis_source": "default"}
            img = Image.open(img_input).convert("RGB")
        else:
            img = img_input.convert("RGB")

        np_img = np.array(img)
        h, w, _ = np_img.shape

        bw = max(2, min(16, min(w, h) // 20))
        top_strip = np_img[:bw, :, :].reshape(-1, 3)
        bot_strip = np_img[-bw:, :, :].reshape(-1, 3)
        left_strip = np_img[:, :bw, :].reshape(-1, 3)
        right_strip = np_img[:, -bw:, :].reshape(-1, 3)

        perim_samples = np.concatenate([top_strip, bot_strip, left_strip, right_strip], axis=0)
        perim_std = float(np.mean(np.std(perim_samples.astype(np.float32), axis=0)))
        perim_median = np.median(perim_samples, axis=0).astype(int)

        def to_hex(rgb):
            return f"#{int(rgb[0]):02x}{int(rgb[1]):02x}{int(rgb[2]):02x}"

        top_color = np.median(top_strip, axis=0).astype(int)
        bot_color = np.median(bot_strip, axis=0).astype(int)
        left_color = np.median(left_strip, axis=0).astype(int)
        right_color = np.median(right_strip, axis=0).astype(int)

        scene_type = "studio_solid" if perim_std < 6.0 else "scenery"

        return {
            "scene_type": scene_type,
            "subject_description": "Detected image content",
            "subject_box": [15, 15, 85, 85],
            "has_sky": (top_color[2] > top_color[0] and top_color[2] > 100),
            "has_ground_or_water": True,
            "horizon_y_percent": 65.0,
            "top_color_hex": to_hex(top_color),
            "bottom_color_hex": to_hex(bot_color),
            "left_color_hex": to_hex(left_color),
            "right_color_hex": to_hex(right_color),
            "dominant_bg_hex": to_hex(perim_median),
            "analysis_source": "local_heuristic",
        }
    except Exception:
        return {"scene_type": "scenery", "analysis_source": "fallback"}
