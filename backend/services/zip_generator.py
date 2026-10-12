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


def create_multi_session_zip_archive(image_ids: list[str]) -> io.BytesIO:
    """
    Create an in-memory ZIP archive containing outputs for multiple uploaded images,
    each neatly organized in its own subfolder named after the original image.
    """
    zip_buffer = io.BytesIO()
    folder_counts: Dict[str, int] = {}
    master_manifest = {
        "application": "Ratio Studio",
        "version": "1.0.0",
        "total_images": len(image_ids),
        "sessions": []
    }

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for image_id in image_ids:
            _, gen_session_dir = get_image_session_dirs(image_id)
            if not os.path.exists(gen_session_dir):
                continue

            metadata_path = os.path.join(gen_session_dir, "metadata.json")
            metadata: Dict[str, Any] = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

            raw_base = metadata.get("original_filename", image_id)
            base_folder = os.path.splitext(raw_base)[0]
            # Clean folder name
            clean_folder = "".join(c for c in base_folder if c.isalnum() or c in ("-", "_")).strip()
            if not clean_folder:
                clean_folder = f"image_{image_id[:8]}"

            # Handle duplicate filenames across images
            count = folder_counts.get(clean_folder, 0)
            folder_counts[clean_folder] = count + 1
            folder_name = clean_folder if count == 0 else f"{clean_folder}_{count + 1}"

            outputs = metadata.get("outputs", [])
            session_entry = {
                "image_id": image_id,
                "folder": folder_name,
                "original_filename": metadata.get("original_filename"),
                "mode": metadata.get("mode"),
                "files": []
            }

            for item in outputs:
                file_name = item.get("file_name")
                file_path = item.get("file_path")
                if file_path and os.path.exists(file_path):
                    zip_file.write(file_path, arcname=f"{folder_name}/{file_name}")
                    session_entry["files"].append(file_name)
                elif file_name:
                    alt_path = os.path.join(gen_session_dir, file_name)
                    if os.path.exists(alt_path):
                        zip_file.write(alt_path, arcname=f"{folder_name}/{file_name}")
                        session_entry["files"].append(file_name)

            master_manifest["sessions"].append(session_entry)

        # Write master manifest
        zip_file.writestr("manifest.json", json.dumps(master_manifest, indent=2))

    zip_buffer.seek(0)
    return zip_buffer

