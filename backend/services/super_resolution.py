"""Real-ESRGAN CNN Super-Resolution Service for Ratio Studio.
Provides high-fidelity general-image super-resolution with tiled inference and master caching.
Preserves original working.png as immutable source files.
"""

import os
import sys
import math
import time
import hashlib
import logging
import threading
from typing import Optional, Tuple, Dict, Any, Union
from PIL import Image, ImageFilter, ImageOps
import numpy as np

logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_DIR = os.path.join(BASE_DIR, "weights")
os.makedirs(WEIGHTS_DIR, exist_ok=True)

# Official Real-ESRGAN model configurations
MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "RealESRGAN_x4plus": {
        "scale": 4,
        "num_in_ch": 3,
        "num_out_ch": 3,
        "num_feat": 64,
        "num_block": 23,
        "num_grow_ch": 32,
        "filename": "RealESRGAN_x4plus.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
    },
    "RealESRGAN_x2plus": {
        "scale": 2,
        "num_in_ch": 3,
        "num_out_ch": 3,
        "num_feat": 64,
        "num_block": 23,
        "num_grow_ch": 32,
        "filename": "RealESRGAN_x2plus.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    },
}

# In-memory singleton model cache
_MODEL_CACHE: Dict[str, Any] = {}
_MODEL_LOCK = threading.Lock()


# -------------------------------------------------------------------------
# PyTorch RRDBNet Architecture (Official Real-ESRGAN Generator)
# -------------------------------------------------------------------------

def _build_rrdbnet_class():
    """Dynamically define RRDBNet if torch is installed."""
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F

        class ResidualDenseBlock_5C(nn.Module):
            def __init__(self, nf=64, gc=32, bias=True):
                super().__init__()
                self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1, bias=bias)
                self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1, bias=bias)
                self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1, bias=bias)
                self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1, bias=bias)
                self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1, bias=bias)
                self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

            def forward(self, x):
                x1 = self.lrelu(self.conv1(x))
                x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
                x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
                x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
                x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
                return x5 * 0.2 + x

        class RRDB(nn.Module):
            def __init__(self, nf=64, gc=32):
                super().__init__()
                self.rdb1 = ResidualDenseBlock_5C(nf, gc)
                self.rdb2 = ResidualDenseBlock_5C(nf, gc)
                self.rdb3 = ResidualDenseBlock_5C(nf, gc)

            def forward(self, x):
                out = self.rdb1(x)
                out = self.rdb2(out)
                out = self.rdb3(out)
                return out * 0.2 + x

        class RRDBNet(nn.Module):
            def __init__(self, num_in_ch=3, num_out_ch=3, scale=4, num_feat=64, num_block=23, num_grow_ch=32):
                super().__init__()
                self.scale = scale
                self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
                self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
                self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
                self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
                if self.scale >= 4:
                    self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
                self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
                self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
                self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

            def forward(self, x):
                fea = self.conv_first(x)
                body_feat = self.conv_body(self.body(fea))
                fea = fea + body_feat
                fea = self.lrelu(self.conv_up1(F.interpolate(fea, scale_factor=2, mode="nearest")))
                if self.scale >= 4:
                    fea = self.lrelu(self.conv_up2(F.interpolate(fea, scale_factor=2, mode="nearest")))
                out = self.conv_last(self.lrelu(self.conv_hr(fea)))
                return out

        return RRDBNet
    except ImportError:
        return None


RRDBNetClass = _build_rrdbnet_class()


def is_torch_available() -> bool:
    """Check if PyTorch is available for neural inference."""
    try:
        import torch
        return True
    except ImportError:
        return False


def get_weights_path(model_name: str = "RealESRGAN_x4plus") -> str:
    """Get the local path for model weights."""
    cfg = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["RealESRGAN_x4plus"])
    return os.path.join(WEIGHTS_DIR, cfg["filename"])


def download_weights_if_needed(model_name: str = "RealESRGAN_x4plus", timeout: int = 60) -> Optional[str]:
    """Download pretrained weights if not already present."""
    local_path = get_weights_path(model_name)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 1024 * 1024:
        return local_path

    cfg = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["RealESRGAN_x4plus"])
    url = cfg["url"]
    temp_path = local_path + ".download"

    try:
        import urllib.request
        logger.info(f"Downloading Real-ESRGAN weights ({model_name}) from {url}...")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RatioStudio/2.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response, open(temp_path, "wb") as out_file:
            chunk_size = 64 * 1024
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)

        if os.path.exists(local_path):
            os.remove(local_path)
        os.rename(temp_path, local_path)
        logger.info(f"Successfully downloaded weights to {local_path} ({os.path.getsize(local_path)} bytes)")
        return local_path
    except Exception as e:
        logger.warning(f"Could not download Real-ESRGAN weights: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return None


def get_super_resolution_model(
    model_name: str = "RealESRGAN_x4plus",
    device: Optional[str] = None
) -> Tuple[Optional[Any], str]:
    """
    Get or load the singleton Real-ESRGAN model.
    Loads once into memory and returns cached model instance.
    """
    if not is_torch_available() or RRDBNetClass is None:
        return None, "PyTorch not available"

    import torch

    target_device = device
    if target_device is None:
        target_device = "cuda" if torch.cuda.is_available() else "cpu"

    cache_key = f"{model_name}:{target_device}"

    with _MODEL_LOCK:
        if cache_key in _MODEL_CACHE:
            return _MODEL_CACHE[cache_key], "ready"

        cfg = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["RealESRGAN_x4plus"])
        weights_path = download_weights_if_needed(model_name)
        if not weights_path or not os.path.exists(weights_path):
            return None, f"Model weights {cfg['filename']} not found or download failed"

        try:
            model = RRDBNetClass(
                num_in_ch=cfg["num_in_ch"],
                num_out_ch=cfg["num_out_ch"],
                scale=cfg["scale"],
                num_feat=cfg["num_feat"],
                num_block=cfg["num_block"],
                num_grow_ch=cfg["num_grow_ch"],
            )

            loadnet = torch.load(weights_path, map_location=torch.device(target_device), weights_only=True)
            if "params_ema" in loadnet:
                keyname = "params_ema"
            elif "params" in loadnet:
                keyname = "params"
            else:
                keyname = None

            state_dict = loadnet[keyname] if keyname else loadnet
            model.load_state_dict(state_dict, strict=True)
            model.eval()
            model.to(target_device)

            _MODEL_CACHE[cache_key] = model
            logger.info(f"Loaded Real-ESRGAN model {model_name} on {target_device} successfully.")
            return model, "ready"
        except Exception as e:
            logger.error(f"Failed to initialize Real-ESRGAN model: {e}")
            return None, f"Model initialization error: {str(e)[:120]}"


# -------------------------------------------------------------------------
# Tiled Inference Engine (Low Memory Consumption)
# -------------------------------------------------------------------------

def run_tiled_inference(
    model: Any,
    img_rgb: np.ndarray,
    tile_size: int = 256,
    tile_pad: int = 16,
    scale: int = 4,
    device: str = "cpu"
) -> np.ndarray:
    """
    Run memory-efficient tiled inference on an RGB image array (H, W, 3) [0..255].
    Returns super-resolved array (H*scale, W*scale, 3) [0..255] uint8.
    """
    import torch

    h, w, c = img_rgb.shape
    # If image is small enough, process in a single pass without tiling
    if tile_size <= 0 or (h <= tile_size and w <= tile_size):
        tensor = torch.from_numpy(img_rgb.transpose(2, 0, 1)).float().unsqueeze(0) / 255.0
        tensor = tensor.to(device)
        with torch.no_grad():
            output = model(tensor)
        out_np = output.squeeze(0).clamp(0, 1).cpu().numpy().transpose(1, 2, 0)
        return (out_np * 255.0).round().astype(np.uint8)

    # Tiled inference with overlap padding
    out_h, out_w = h * scale, w * scale
    out_img = np.zeros((out_h, out_w, c), dtype=np.uint8)

    tiles_x = math.ceil(w / tile_size)
    tiles_y = math.ceil(h / tile_size)

    for yi in range(tiles_y):
        for xi in range(tiles_x):
            # Tile bounding box in original image
            x0 = xi * tile_size
            y0 = yi * tile_size
            x1 = min(x0 + tile_size, w)
            y1 = min(y0 + tile_size, h)

            # Padded coordinates
            px0 = max(x0 - tile_pad, 0)
            py0 = max(y0 - tile_pad, 0)
            px1 = min(x1 + tile_pad, w)
            py1 = min(y1 + tile_pad, h)

            # Crop padded tile
            tile = img_rgb[py0:py1, px0:px1, :]
            tile_tensor = torch.from_numpy(tile.transpose(2, 0, 1)).float().unsqueeze(0) / 255.0
            tile_tensor = tile_tensor.to(device)

            with torch.no_grad():
                out_tile = model(tile_tensor)

            out_tile_np = out_tile.squeeze(0).clamp(0, 1).cpu().numpy().transpose(1, 2, 0)
            out_tile_np = (out_tile_np * 255.0).round().astype(np.uint8)

            # Calculate crop coordinates inside output tile (accounting for padding)
            cut_left = (x0 - px0) * scale
            cut_top = (y0 - py0) * scale
            cut_right = cut_left + (x1 - x0) * scale
            cut_bottom = cut_top + (y1 - y0) * scale

            cropped_tile = out_tile_np[cut_top:cut_bottom, cut_left:cut_right, :]

            # Paste into destination
            dst_x0 = x0 * scale
            dst_y0 = y0 * scale
            dst_x1 = dst_x0 + (x1 - x0) * scale
            dst_y1 = dst_y0 + (y1 - y0) * scale
            out_img[dst_y0:dst_y1, dst_x0:dst_x1, :] = cropped_tile

    return out_img


def fallback_super_resolution(
    img: Image.Image,
    scale: int = 4
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    High-quality algorithmic fallback when CNN model is unavailable.
    Uses Lanczos resampling with edge-adaptive unsharp sharpening.
    """
    orig_w, orig_h = img.size
    target_w = orig_w * scale
    target_h = orig_h * scale

    has_alpha = (img.mode == "RGBA")
    if has_alpha:
        # Separate RGB and alpha
        alpha = img.split()[-1].resize((target_w, target_h), Image.Resampling.BICUBIC)
        rgb_img = img.convert("RGB").resize((target_w, target_h), Image.Resampling.LANCZOS)
        enhanced_rgb = rgb_img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=45, threshold=2))
        res = enhanced_rgb.convert("RGBA")
        res.putalpha(alpha)
    else:
        rgb_img = img.convert("RGB").resize((target_w, target_h), Image.Resampling.LANCZOS)
        res = rgb_img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=45, threshold=2))

    meta = {
        "status": "fallback",
        "provider": "studio_fallback",
        "model": "lanczos_unsharp",
        "scale": scale,
        "is_neural_sr": False,
        "description": "High-quality Lanczos edge-enhanced fallback (Real-ESRGAN unavailable).",
        "original_size": [orig_w, orig_h],
        "enhanced_size": [target_w, target_h],
    }
    return res, meta


def enhance_image_with_realesrgan(
    img: Image.Image,
    model_name: str = "RealESRGAN_x4plus",
    scale: Optional[int] = None,
    tile_size: int = 256,
    tile_pad: int = 16,
    device: Optional[str] = None
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Enhance an image using Real-ESRGAN super-resolution.
    Uses tiled inference to maintain low RAM usage.
    Handles transparency and falls back gracefully if model is unavailable.
    """
    cfg = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["RealESRGAN_x4plus"])
    effective_scale = scale or cfg["scale"]

    # Check if neural model can be loaded
    model, load_status = get_super_resolution_model(model_name=model_name, device=device)
    if model is None:
        logger.info(f"Using fallback super-resolution: {load_status}")
        return fallback_super_resolution(img, scale=effective_scale)

    import torch
    target_device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    orig_w, orig_h = img.size
    is_rgba = (img.mode == "RGBA")

    try:
        t0 = time.time()
        rgb_pil = img.convert("RGB")
        rgb_np = np.array(rgb_pil)

        out_rgb_np = run_tiled_inference(
            model=model,
            img_rgb=rgb_np,
            tile_size=tile_size,
            tile_pad=tile_pad,
            scale=effective_scale,
            device=target_device
        )

        out_pil = Image.fromarray(out_rgb_np)

        if is_rgba:
            alpha = img.split()[-1]
            out_alpha = alpha.resize(out_pil.size, Image.Resampling.BICUBIC)
            out_pil = out_pil.convert("RGBA")
            out_pil.putalpha(out_alpha)

        elapsed = time.time() - t0
        meta = {
            "status": "ready",
            "provider": "realesrgan",
            "model": model_name,
            "scale": effective_scale,
            "is_neural_sr": True,
            "elapsed_seconds": round(elapsed, 3),
            "original_size": [orig_w, orig_h],
            "enhanced_size": list(out_pil.size),
            "description": f"Real-ESRGAN CNN {effective_scale}x super-resolution enhanced foreground (tiled {tile_size}px).",
        }
        return out_pil, meta
    except Exception as e:
        logger.warning(f"Real-ESRGAN execution failed: {e}. Falling back to algorithmic enhancement.")
        return fallback_super_resolution(img, scale=effective_scale)


# -------------------------------------------------------------------------
# Caching & Master Management
# -------------------------------------------------------------------------

def get_or_create_enhanced_master(
    image_id: str,
    source_img: Image.Image,
    version: int = 1,
    model_name: str = "RealESRGAN_x4plus",
    scale: int = 4,
    tile_size: int = 256,
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Get cached super-resolved master copy or create and cache it safely.
    NEVER overwrites working.png.
    Cache key format: enhanced_v{version}_{model_name}_x{scale}.png in orig_session_dir.
    """
    orig_session_dir = os.path.join(BASE_DIR, "storage", "original", image_id)
    os.makedirs(orig_session_dir, exist_ok=True)

    cache_filename = f"enhanced_v{version}_{model_name}_x{scale}.png"
    cache_path = os.path.join(orig_session_dir, cache_filename)

    # 1. Return from disk cache if exists
    if os.path.exists(cache_path):
        try:
            with Image.open(cache_path) as cached_img:
                # Load fully into memory
                cached_copy = cached_img.copy()
                meta = {
                    "status": "ready",
                    "provider": "realesrgan",
                    "model": model_name,
                    "scale": scale,
                    "is_neural_sr": True,
                    "is_cached": True,
                    "cache_file": cache_filename,
                    "enhanced_size": list(cached_copy.size),
                    "description": f"Loaded cached Real-ESRGAN master (v{version}).",
                }
                return cached_copy, meta
        except Exception as e:
            logger.warning(f"Failed to read cached enhanced master: {e}")

    # 2. Generate enhanced master
    enhanced_img, meta = enhance_image_with_realesrgan(
        img=source_img,
        model_name=model_name,
        scale=scale,
        tile_size=tile_size,
    )

    # 3. Save to dedicated cache file (never touching working.png)
    try:
        enhanced_img.save(cache_path, format="PNG")
        meta["cache_file"] = cache_filename
        meta["is_cached"] = False
    except Exception as e:
        logger.warning(f"Could not persist enhanced master to cache: {e}")

    return enhanced_img, meta
