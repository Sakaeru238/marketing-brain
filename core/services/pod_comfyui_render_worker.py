from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from .pod_pipeline_utils import safe_name, utc_now, write_json


STEP_NAME = "05_comfyui_render_worker"


class PodComfyUIRenderWorker:
    """
    Dispatches Step [4] render requests to a ComfyUI render endpoint.

    Default mode is dry_run so the production pipeline can validate contracts
    before a render worker endpoint is available.
    """

    def __init__(self, *, settings: dict[str, Any] | None = None) -> None:
        self.settings = settings or {}
        comfyui_settings = self.settings.get("comfyui") or {}
        self.mode = str(
            os.getenv("POD_COMFYUI_MODE")
            or comfyui_settings.get("mode")
            or "dry_run"
        ).strip().lower()
        self.endpoint_url = str(
            os.getenv("COMFYUI_RENDER_ENDPOINT_URL")
            or comfyui_settings.get("render_endpoint_url")
            or ""
        ).strip()
        self.timeout_seconds = int(comfyui_settings.get("timeout_seconds") or 600)

    def run(
        self,
        *,
        brand_id: str,
        campaign_id: str,
        render_request_bundle: dict[str, Any],
        output_dir: str | Path,
        attempt_no: int = 1,
    ) -> dict[str, Any]:
        requests_payload = list(render_request_bundle.get("requests") or [])
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        results = []
        for index, request_payload in enumerate(requests_payload, start=1):
            result = self._render_one(
                brand_id=brand_id,
                campaign_id=campaign_id,
                request_payload=request_payload,
                output_dir=output_root,
                sequence=index,
                attempt_no=attempt_no,
            )
            results.append(result)

        successful = [
            item
            for item in results
            if item.get("status") in {"rendered", "submitted", "dry_run"}
        ]
        return {
            "stage": "comfyui_render_worker",
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "attempt_no": attempt_no,
            "mode": self.mode,
            "status": "success" if len(successful) == len(results) else "partial_or_failed",
            "started_or_ran_at": utc_now(),
            "requests_received": len(requests_payload),
            "results_count": len(results),
            "results": results,
        }

    def _render_one(
        self,
        *,
        brand_id: str,
        campaign_id: str,
        request_payload: dict[str, Any],
        output_dir: Path,
        sequence: int,
        attempt_no: int,
    ) -> dict[str, Any]:
        output_group = str(request_payload.get("output_group") or f"group_{sequence}")
        job_id = str(request_payload.get("job_id") or "").strip()
        if not job_id:
            job_id = f"POD_{safe_name(brand_id)}_{safe_name(campaign_id)}_{safe_name(output_group)}_A{attempt_no:02d}_{sequence:02d}"
            request_payload["job_id"] = job_id
        request_payload.setdefault("metadata", {})
        request_payload["metadata"]["attempt_no"] = attempt_no

        request_file = write_json(
            output_dir / f"{safe_name(job_id)}_render_request.json",
            request_payload,
        )

        if self.mode == "dry_run" or not self.endpoint_url:
            return {
                "job_id": job_id,
                "output_group": output_group,
                "status": "dry_run",
                "render_request_file": str(request_file),
                "generated_images": [],
                "message": "Render request prepared but not sent. Configure COMFYUI_RENDER_ENDPOINT_URL and POD_COMFYUI_MODE=endpoint to render.",
                "completed_at": utc_now(),
            }

        if self.mode != "endpoint":
            return {
                "job_id": job_id,
                "output_group": output_group,
                "status": "error",
                "render_request_file": str(request_file),
                "generated_images": [],
                "error": f"Unsupported ComfyUI render mode: {self.mode}",
                "completed_at": utc_now(),
            }

        try:
            response = requests.post(
                self.endpoint_url,
                json=request_payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            response_payload = response.json()
            response_file = write_json(
                output_dir / f"{safe_name(job_id)}_render_response.json",
                response_payload,
            )
            return self._normalize_endpoint_response(
                job_id=job_id,
                output_group=output_group,
                request_file=request_file,
                response_file=response_file,
                response_payload=response_payload,
            )
        except Exception as exc:
            return {
                "job_id": job_id,
                "output_group": output_group,
                "status": "error",
                "render_request_file": str(request_file),
                "generated_images": [],
                "error": str(exc),
                "completed_at": utc_now(),
            }

    def _normalize_endpoint_response(
        self,
        *,
        job_id: str,
        output_group: str,
        request_file: Path,
        response_file: Path,
        response_payload: dict[str, Any],
    ) -> dict[str, Any]:
        images = (
            response_payload.get("generated_images")
            or response_payload.get("images")
            or response_payload.get("image_paths")
            or []
        )
        if isinstance(images, str):
            images = [images]
        normalized_images = [
            item if isinstance(item, dict) else {"path": str(item)}
            for item in images
        ]
        status = str(response_payload.get("status") or "").strip().lower()
        if status not in {"rendered", "submitted", "success"}:
            status = "rendered" if normalized_images else "submitted"
        if status == "success":
            status = "rendered"
        return {
            "job_id": job_id,
            "output_group": output_group,
            "status": status,
            "render_request_file": str(request_file),
            "render_response_file": str(response_file),
            "generated_images": normalized_images,
            "raw_response_status": response_payload.get("status"),
            "completed_at": utc_now(),
        }
