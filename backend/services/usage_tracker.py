"""Usage Tracking & Cloudflare Workers AI Observability Service for Ratio Studio.
Tracks real-time metrics for Cloudflare API invocations, response latencies,
Ray IDs, HTTP status codes, Neurons response headers, and local fallback usage.

Does NOT count Groq vision tokens or local OpenCV processing as Cloudflare Neurons.
Does NOT guess or estimate unverified Neurons.
"""

import os
import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class UsageTracker:
    """Thread-safe persistent usage statistics tracker."""

    def __init__(self, storage_file: Optional[str] = None):
        self._lock = threading.Lock()
        if storage_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(base_dir, "storage")
            os.makedirs(storage_dir, exist_ok=True)
            self._storage_file = os.path.join(storage_dir, "usage_stats.json")
        else:
            self._storage_file = storage_file

        self._stats: Dict[str, Any] = {
            "total_uploads": 0,
            "total_ratios_generated": 0,
            "cloudflare_requests": 0,
            "successful_cloudflare_requests": 0,
            "failed_cloudflare_requests": 0,
            "local_fallback_executions": 0,
            "total_cloudflare_duration_ms": 0.0,
            "average_response_time_ms": 0.0,
            "model_name": "@cf/runwayml/stable-diffusion-v1-5-inpainting",
            "last_ray_id": None,
            "last_request_timestamp": None,
            "last_neurons_header": None,
            "actual_neurons_status": "Cloudflare reports cf-ai-neurons: 0.00. The model @cf/runwayml/stable-diffusion-v1-5-inpainting is in Beta ($0.00 per step / zero-rated).",
            "recent_events": [],
        }
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if os.path.exists(self._storage_file):
            try:
                with open(self._storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._stats.update(data)
            except Exception:
                pass

    def _save_to_disk(self) -> None:
        try:
            temp_file = f"{self._storage_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, indent=2)
            os.replace(temp_file, self._storage_file)
        except Exception:
            pass

    def record_upload(self) -> None:
        with self._lock:
            self._stats["total_uploads"] = int(self._stats.get("total_uploads", 0)) + 1
            self._save_to_disk()

    def record_ratios_generated(self, count: int = 5) -> None:
        with self._lock:
            self._stats["total_ratios_generated"] = int(self._stats.get("total_ratios_generated", 0)) + count
            self._save_to_disk()

    def record_cloudflare_result(
        self,
        success: bool,
        status_code: int,
        duration_ms: float,
        ray_id: str,
        content_type: str,
        response_size: int,
        neurons_header: Optional[str],
        target_w: int,
        target_h: int,
        error_msg: Optional[str] = None,
    ) -> None:
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._stats["cloudflare_requests"] = int(self._stats.get("cloudflare_requests", 0)) + 1

            if success:
                self._stats["successful_cloudflare_requests"] = int(self._stats.get("successful_cloudflare_requests", 0)) + 1
            else:
                self._stats["failed_cloudflare_requests"] = int(self._stats.get("failed_cloudflare_requests", 0)) + 1

            prev_duration = float(self._stats.get("total_cloudflare_duration_ms", 0.0))
            new_duration = prev_duration + duration_ms
            self._stats["total_cloudflare_duration_ms"] = new_duration

            total_reqs = self._stats["cloudflare_requests"]
            self._stats["average_response_time_ms"] = round(new_duration / max(1, total_reqs), 1)

            if ray_id and ray_id != "N/A":
                self._stats["last_ray_id"] = ray_id
            self._stats["last_request_timestamp"] = now_iso

            if neurons_header:
                self._stats["last_neurons_header"] = neurons_header

            # Append to recent events (ring buffer max 50 entries)
            event_type = "CLOUDFLARE_SUCCESS" if success else "CLOUDFLARE_FAILED"
            event = {
                "timestamp": now_iso,
                "event_type": event_type,
                "ratio": f"{target_w}x{target_h}",
                "status_code": status_code,
                "duration_ms": duration_ms,
                "ray_id": ray_id,
                "content_type": content_type,
                "response_size_bytes": response_size,
                "cf_ai_neurons": neurons_header or "0.00",
                "error": error_msg,
            }
            events = self._stats.get("recent_events", [])
            events.insert(0, event)
            self._stats["recent_events"] = events[:50]

            self._save_to_disk()

    def record_fallback_used(
        self,
        target_w: int,
        target_h: int,
        reason: str,
        failed_status_or_exception: Optional[str] = None,
    ) -> None:
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._stats["local_fallback_executions"] = int(self._stats.get("local_fallback_executions", 0)) + 1

            event = {
                "timestamp": now_iso,
                "event_type": "LOCAL_FALLBACK_USED",
                "ratio": f"{target_w}x{target_h}",
                "status_code": None,
                "duration_ms": None,
                "ray_id": None,
                "reason": reason,
                "exception": failed_status_or_exception,
            }
            events = self._stats.get("recent_events", [])
            events.insert(0, event)
            self._stats["recent_events"] = events[:50]

            self._save_to_disk()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)

    def reset_stats(self) -> Dict[str, Any]:
        with self._lock:
            self._stats = {
                "total_uploads": 0,
                "total_ratios_generated": 0,
                "cloudflare_requests": 0,
                "successful_cloudflare_requests": 0,
                "failed_cloudflare_requests": 0,
                "local_fallback_executions": 0,
                "total_cloudflare_duration_ms": 0.0,
                "average_response_time_ms": 0.0,
                "model_name": "@cf/runwayml/stable-diffusion-v1-5-inpainting",
                "last_ray_id": None,
                "last_request_timestamp": None,
                "last_neurons_header": None,
                "actual_neurons_status": "Cloudflare reports cf-ai-neurons: 0.00. The model @cf/runwayml/stable-diffusion-v1-5-inpainting is in Beta ($0.00 per step / zero-rated).",
                "recent_events": [],
            }
            self._save_to_disk()
            return dict(self._stats)


# Global singleton instance
usage_tracker = UsageTracker()
