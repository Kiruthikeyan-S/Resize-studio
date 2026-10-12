"""ZIP archive generator for Ratio Studio outputs."""

import os
import json
import zipfile
import io
from typing import Dict, Any, Optional
from services.image_processor import get_image_session_dirs


def create_zip_archive(image_id: str) -> io.BytesIO:
    """
    Create an in-memory ZIP archive containing all 5 output images
    and a manifest.json describing output dimensions and processing modes.
    """
    _, gen_session_dir = get_image_session_dirs(image_id)
    if not os.path.exists(gen_session_dir):
        raise FileNotFoundError(f"Generated outputs not found for session {image_id}")

    metadata_path = os.path.join(gen_session_dir, "metadata.json")
    metadata: Dict[str, Any] = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        outputs = metadata.get("outputs", [])
        
        # Manifest data specifically formatted for user inspection
        user_manifest = {
            "application": "Ratio Studio",
            "version": "1.0.0",
            "original_filename": metadata.get("original_filename", "image"),
            "processing_mode": metadata.get("mode", "smart_crop"),
            "export_format": metadata.get("export_format", "jpeg"),
            "quality": metadata.get("quality", 90),
            "generated_at": metadata.get("generated_at"),
            "files": []
        }

        # Add image files to the archive
        for item in outputs:
            file_name = item.get("file_name")
            file_path = item.get("file_path")
            if file_path and os.path.exists(file_path):
                zip_file.write(file_path, arcname=file_name)
                user_manifest["files"].append({
                    "filename": file_name,
                    "ratio": item.get("ratio_key"),
                    "name": item.get("name"),
                    "dimensions": f"{item.get('width')}x{item.get('height')}",
                    "orientation": item.get("orientation"),
                    "size_bytes": item.get("file_size"),
                    "mode": item.get("mode")
                })
            elif file_name:
                alt_path = os.path.join(gen_session_dir, file_name)
                if os.path.exists(alt_path):
                    zip_file.write(alt_path, arcname=file_name)
                    user_manifest["files"].append({
                        "filename": file_name,
                        "ratio": item.get("ratio_key"),
                        "name": item.get("name"),
                        "dimensions": f"{item.get('width')}x{item.get('height')}",
                        "orientation": item.get("orientation"),
                        "size_bytes": os.path.getsize(alt_path),
                        "mode": item.get("mode")
                    })

        # Add manifest.json to the ZIP archive
        manifest_str = json.dumps(user_manifest, indent=2)
        zip_file.writestr("manifest.json", manifest_str)

    zip_buffer.seek(0)
    return zip_buffer
