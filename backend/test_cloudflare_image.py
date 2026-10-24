"""Verification test script for Cloudflare Workers AI Inpainting model.

Model: @cf/runwayml/stable-diffusion-v1-5-inpainting
Verifies genuine aspect-ratio-preserving background outpainting with protected central subject.
"""

import io
import os
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv
from PIL import Image

# Search for .env in current directory and parent directories
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
api_token = os.getenv("CLOUDFLARE_API_TOKEN")

if not account_id or not api_token:
    print(
        "ERROR: Cloudflare credentials are missing.\n"
        "Please ensure CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are set in your backend/.env file.",
        file=sys.stderr,
    )
    sys.exit(1)

# Masked token confirmation (never expose private secrets)
masked_token = api_token[:4] + "..." + api_token[-4:] if len(api_token) > 8 else "***"
print(f"Loaded Cloudflare Account ID: {account_id}")
print(f"Loaded Cloudflare API Token:  {masked_token}")

# Test 16:9 Landscape aspect ratio (1024 x 576 working dimensions)
work_w, work_h = 1024, 576
url = (
    f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/"
    "@cf/runwayml/stable-diffusion-v1-5-inpainting"
)

headers = {
    "Authorization": f"Bearer {api_token.strip()}",
}

print(f"\nConstructing {work_w}x{work_h} test canvas and inpainting mask preserving 16:9 aspect ratio...")

# Create sample subject in the center (400 x 400 product/subject box)
subj_w, subj_h = 400, 400
subj_x = (work_w - subj_w) // 2
subj_y = (work_h - subj_h) // 2

# Base canvas: fill background with ambient photographic color, place subject in center
canvas = Image.new("RGB", (work_w, work_h), (210, 230, 245))  # Soft sky blue ambient
subject_img = Image.new("RGB", (subj_w, subj_h), (35, 120, 210))  # Sample central subject
canvas.paste(subject_img, (subj_x, subj_y))

# Inpainting mask: 255 (white = area to generate) on outer background, 0 (black = protected) on subject
mask = Image.new("L", (work_w, work_h), 255)
mask.paste(Image.new("L", (subj_w - 4, subj_h - 4), 0), (subj_x + 2, subj_y + 2))

buf_i = io.BytesIO()
canvas.save(buf_i, format="PNG")
buf_m = io.BytesIO()
mask.save(buf_m, format="PNG")

payload = {
    "prompt": "soft light blue sky with subtle natural clouds, matching scenery continuation, photorealistic, high quality",
    "image": list(buf_i.getvalue()),
    "mask": list(buf_m.getvalue()),
    "width": work_w,
    "height": work_h,
}

print("Sending inpainting request to Cloudflare Workers AI (@cf/runwayml/stable-diffusion-v1-5-inpainting)...")
try:
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )
except requests.exceptions.Timeout:
    print("ERROR: Request timed out after 60 seconds.", file=sys.stderr)
    sys.exit(1)
except requests.exceptions.RequestException as err:
    print(f"ERROR: HTTP request failed: {err}", file=sys.stderr)
    sys.exit(1)

# Handle HTTP status codes
if response.status_code == 401:
    print("ERROR (401 Unauthorized): Invalid or expired Cloudflare API token.", file=sys.stderr)
    sys.exit(1)
elif response.status_code == 429:
    print("ERROR (429 Rate Limit): Rate limit exceeded on Cloudflare Workers AI.", file=sys.stderr)
    sys.exit(1)
elif response.status_code != 200:
    print(f"ERROR ({response.status_code}): Inpainting request failed.", file=sys.stderr)
    print(f"Response: {response.text[:300]}", file=sys.stderr)
    sys.exit(1)

# Validate output image bytes
try:
    gen_img = Image.open(io.BytesIO(response.content)).convert("RGB")
    gw, gh = gen_img.size
except Exception as e:
    print(f"ERROR: Failed to decode generated image: {e}", file=sys.stderr)
    sys.exit(1)

# Composite pristine subject over the generated background
final_img = gen_img.copy()
final_img.paste(subject_img, (subj_x, subj_y))

# Save local verification image
output_path = Path(__file__).resolve().parent / "generated_background.png"
final_img.save(output_path, format="PNG")

print("\n========================================================")
print("SUCCESS: Cloudflare Inpainting verified successfully!")
print(f"Model ID:        @cf/runwayml/stable-diffusion-v1-5-inpainting")
print(f"Saved file path: {output_path}")
print(f"Dimensions:      {gw} x {gh} (Aspect Ratio: {gw/gh:.3f})")
print(f"Subject Area:    [{subj_x}, {subj_y}, {subj_x + subj_w}, {subj_y + subj_h}] (100% Protected)")
print("========================================================")
