"""ZIP archive generator for Ratio Studio outputs."""

import os
import json
import zipfile
import io
from typing import Dict, Any, Optional
from services.image_processor import get_image_session_dirs
from services.crop_engine import all_selection_ids


class SelectionError(ValueError):
    """Invalid client selection (unknown/duplicate ids, stale revision)."""


class MissingOutputError(FileNotFoundError):
    """A selected generated file no longer exists on disk."""


def create_selected_zip_archive(
    image_id: str,
    selection_ids: list,
    revision: Optional[int] = None,
) -> io.BytesIO:
    """
    Build a ZIP containing ONLY the selected '<ratio>:<size>' outputs from the latest generation.
    Files are resolved exclusively from the server-side manifest (never client paths).
    """
    if not selection_ids:
        raise SelectionError("No images selected.")

    from services.crop_engine import all_comparison_selection_ids
    valid_ids = set(all_selection_ids()) | set(all_comparison_selection_ids())
    seen = set()
    for sid in selection_ids:
        if not isinstance(sid, str) or sid not in valid_ids:
            raise SelectionError(f"Invalid selection identifier: {sid!r}")
        if sid in seen:
            raise SelectionError(f"Duplicate selection: {sid}")
        seen.add(sid)

    _, gen_session_dir = get_image_session_dirs(image_id)
    metadata_path = os.path.join(gen_session_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Generated outputs not found for session {image_id}")
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata: Dict[str, Any] = json.load(f)

    current_revision = metadata.get("revision")
    if revision is not None and revision != current_revision:
        raise SelectionError(
            f"Stale generation revision {revision}; current revision is {current_revision}. "
            "Please refresh and select again."
        )

    by_id = {}
    for v in metadata.get("variants", []):
        sid = v.get("selection_id", "")
        by_id[sid] = v
        if "legacy_selection_id" in v:
            by_id[v["legacy_selection_id"]] = v
        if sid.startswith("standard:"):
            bare_id = sid.split("standard:", 1)[1]
            if bare_id not in by_id:
                by_id[bare_id] = v
        elif not sid.startswith("ai:") and not sid.startswith("groq:"):
            std_id = f"standard:{sid}"
            if std_id not in by_id:
                by_id[std_id] = v

    gen_root = os.path.realpath(gen_session_dir)

    resolved = []
    for sid in selection_ids:
        record = by_id.get(sid)
        if not record and not sid.startswith("standard:") and not sid.startswith("ai:") and not sid.startswith("groq:"):
            record = by_id.get(f"standard:{sid}")
        if not record:
            raise MissingOutputError(f"Output {sid} has not been generated.")
        
        # Ensure only successfully generated images enter the ZIP
        if record.get("status") in ["failed", "unavailable"]:
            raise SelectionError(f"Selected image {sid} cannot be downloaded because generation status is {record.get('status')}.")

        path = os.path.realpath(record.get("file_path", ""))
        if os.path.commonpath([gen_root, path]) != gen_root or not os.path.isfile(path):
            raise MissingOutputError(f"Generated file for {sid} is missing.")
        resolved.append((record, path))

    manifest = {
        "application": "Ratio Studio",
        "version": "1.0.0",
        "original_filename": metadata.get("original_filename", "image"),
        "export_format": metadata.get("export_format", "jpeg"),
        "quality": metadata.get("quality", 90),
        "generation_revision": current_revision,
        "generated_at": metadata.get("generated_at"),
        "selected_count": len(resolved),
        "files": [],
    }

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for record, path in resolved:
            zf.write(path, arcname=record["file_name"])
            manifest["files"].append({
                "filename": record["file_name"],
                "selection_id": record["selection_id"],
                "ratio": record["ratio_name"],
                "size": record["size_label"],
                "dimensions": f"{record['width']}x{record['height']}",
                "size_bytes": os.path.getsize(path),
            })
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    zip_buffer.seek(0)
    return zip_buffer


def create_zip_archive(image_id: str, mode: Optional[str] = None) -> io.BytesIO:
    """
    Create an in-memory ZIP archive containing all 5 output images
    and a manifest.json describing output dimensions and processing modes.
    Respects mode parameter if specified.
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
        if mode and "outputs_by_mode" in metadata and mode in metadata["outputs_by_mode"]:
            outputs = metadata["outputs_by_mode"][mode]
            effective_mode = mode
        else:
            outputs = metadata.get("outputs", [])
            effective_mode = metadata.get("mode", "smart_crop")
        
        # Manifest data specifically formatted for user inspection
        user_manifest = {
            "application": "Ratio Studio",
            "version": "1.0.0",
            "original_filename": metadata.get("original_filename", "image"),
            "processing_mode": effective_mode,
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


def create_multi_session_zip_archive(image_ids: list[str], mode: Optional[str] = None) -> io.BytesIO:
    """
    Create an in-memory ZIP archive containing outputs for multiple uploaded images,
    each neatly organized in its own subfolder named after the original image.
    Respects mode parameter if specified.
    """
    zip_buffer = io.BytesIO()
    folder_counts: Dict[str, int] = {}
    master_manifest = {
        "application": "Ratio Studio",
        "version": "1.0.0",
        "total_images": len(image_ids),
        "mode": mode or "all",
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

            if mode and "outputs_by_mode" in metadata and mode in metadata["outputs_by_mode"]:
                outputs = metadata["outputs_by_mode"][mode]
                effective_mode = mode
            else:
                outputs = metadata.get("outputs", [])
                effective_mode = metadata.get("mode", "smart_crop")

            session_entry = {
                "image_id": image_id,
                "folder": folder_name,
                "original_filename": metadata.get("original_filename"),
                "mode": effective_mode,
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

