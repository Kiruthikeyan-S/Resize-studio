"""Optional Groq Vision Analysis Service for Ratio Studio.
Integrates Groq Vision API to extract subject details, approximate coordinates, and crop risks.
Fails gracefully to non-Groq fallback pipeline if API key is missing or unavailable.
"""

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
    Analyze image using Groq Vision API (e.g. llama-3.2-11b-vision-preview).
    Returns structured SubjectAnalysis or None if unavailable.
    Never raises an uncaught exception to caller.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not GROQ_AVAILABLE or not api_key:
        return None

    if not os.path.exists(image_path):
        return None

    try:
        # Resize to max 1024px before sending to vision API for speed and bandwidth efficiency
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

        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
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

        content = response.choices[0].message.content
        if not content:
            return None

        parsed = json.loads(content)
        analysis = SubjectAnalysis(**parsed)
        return analysis

    except Exception:
        # Graceful fallback: return None on rate limits, timeouts, or parsing errors
        return None
