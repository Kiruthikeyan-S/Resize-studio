"""Test script for Cloudflare Workers AI FLUX.1 Schnell model.

Model: @cf/black-forest-labs/flux-1-schnell
Generates a commercial product photography background.
"""

import base64
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

# Masked token confirmation (never print the secret token)
masked_token = api_token[:4] + "..." + api_token[-4:] if len(api_token) > 8 else "***"
print(f"Loaded Cloudflare Account ID: {account_id}")
print(f"Loaded Cloudflare API Token:  {masked_token}")

url = (
    f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/"
    "@cf/black-forest-labs/flux-1-schnell"
)

headers = {
    "Authorization": f"Bearer {api_token.strip()}",
    "Content-Type": "application/json",
}

# Strictly supported parameters for @cf/black-forest-labs/flux-1-schnell
payload = {
    "prompt": (
        "a premium commercial product photography background with a warm beige studio, "
        "soft diffused lighting, subtle realistic shadows, an empty center, "
        "and no product, text, or logos"
    ),
    "steps": 4,
}

print("\nSending request to Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell)...")
try:
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120,
    )
except requests.exceptions.Timeout:
    print("ERROR: Request timed out after 120 seconds.", file=sys.stderr)
    sys.exit(1)
except requests.exceptions.ConnectionError as err:
    print(f"ERROR: Network connection failed: {err}", file=sys.stderr)
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
    print(f"ERROR ({response.status_code}): Request failed.", file=sys.stderr)
    try:
        err_json = response.json()
        print(f"Cloudflare error response: {err_json}", file=sys.stderr)
    except Exception:
        print(f"Response body: {response.text[:300]}", file=sys.stderr)
    sys.exit(1)

# Decode response
image_bytes = None
content_type = response.headers.get("content-type", "")

if "application/json" in content_type:
    try:
        data = response.json()
    except Exception as e:
        print(f"ERROR: Failed to parse response JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not data.get("success", True):
        errors = data.get("errors", "Unknown error")
        print(f"ERROR: Cloudflare returned failure: {errors}", file=sys.stderr)
        sys.exit(1)

    result = data.get("result", {})
    image_base64 = result.get("image")
    if not image_base64:
        print("ERROR: Response JSON did not contain 'result.image'.", file=sys.stderr)
        print(f"Available keys in result: {list(result.keys())}", file=sys.stderr)
        sys.exit(1)

    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        print(f"ERROR: Failed to base64-decode image: {e}", file=sys.stderr)
        sys.exit(1)
elif "image/" in content_type:
    # Direct binary response
    image_bytes = response.content
else:
    # Try parsing as JSON first
    try:
        data = response.json()
        if data.get("result", {}).get("image"):
            image_bytes = base64.b64decode(data["result"]["image"])
    except Exception:
        image_bytes = response.content

if not image_bytes:
    print("ERROR: No image bytes received.", file=sys.stderr)
    sys.exit(1)

# Validate decoded image with Pillow
try:
    pil_img = Image.open(io.BytesIO(image_bytes))
    img_format = (pil_img.format or "JPEG").lower()
    width, height = pil_img.size
except Exception as e:
    print(f"ERROR: Failed to validate decoded image: {e}", file=sys.stderr)
    sys.exit(1)

# Determine output filename
ext = "png" if img_format == "png" else "jpg"
output_filename = f"generated_background.{ext}"
output_path = Path(__file__).resolve().parent / output_filename

with open(output_path, "wb") as f:
    f.write(image_bytes)

# Also ensure generated_background.png is available for convenience
png_path = Path(__file__).resolve().parent / "generated_background.png"
pil_img.save(png_path, format="PNG")

print("\n========================================================")
print("SUCCESS: Image generated and verified successfully!")
print(f"Saved native file:  {output_path}")
print(f"Saved PNG copy:     {png_path}")
print(f"Dimensions:         {width} x {height}")
print(f"Native format:      {img_format.upper()}")
print(f"File size:          {len(image_bytes) / 1024:.1f} KB")
print("========================================================")
