from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pod_pipeline_utils import utc_now, write_json


STEP_NAME = "07_human_review"
VALID_DECISIONS = {"approved", "rejected"}
VALID_REJECTION_ROUTES = {"step_4_open_design_translation", "step_2_design_brief"}


class PodHumanReviewService:
    def build_review_package(
        self,
        *,
        brand_id: str,
        campaign_id: str,
        strategy_output: dict[str, Any],
        design_brief: dict[str, Any],
        translation_output: dict[str, Any],
        render_result: dict[str, Any],
        visual_eval_result: dict[str, Any],
        output_file: str | Path,
    ) -> dict[str, Any]:
        package = {
            "stage": "pod_human_review",
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "status": "pending_human_review",
            "created_at": utc_now(),
            "review_instructions": [
                "Review generated image files or render worker URLs in render_result.results.",
                "Set decision to approved or rejected.",
                "If rejected, set rejection_route to step_4_open_design_translation for prompt/payload issues or step_2_design_brief for brief/strategy interpretation issues.",
                "Add rejection_reasons and requested_changes before rerunning the orchestrator.",
            ],
            "review_decision_template": {
                "decision": "",
                "reviewer": "",
                "reviewed_at": "",
                "rejection_route": "step_4_open_design_translation",
                "rejection_reasons": [],
                "requested_changes": [],
                "approved_notes": "",
            },
            "strategy_summary": strategy_output.get("strategy_summary") or {},
            "design_objective": design_brief.get("design_objective") or {},
            "output_groups": design_brief.get("output_groups") or {},
            "chatgpt_image_prompts": translation_output.get("chatgpt_image_prompts") or [],
            "render_result": render_result,
            "visual_eval_result": visual_eval_result,
        }
        write_json(output_file, package)
        return package

    def load_review_decision(self, review_decision_file: str | Path) -> dict[str, Any]:
        path = Path(review_decision_file)
        if not path.exists():
            raise FileNotFoundError(f"Human review decision file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Human review decision file must contain a JSON object.")
        return self.normalize_decision(payload)

    def normalize_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        decision = str(payload.get("decision") or "").strip().lower()
        if decision not in VALID_DECISIONS:
            raise ValueError("Human review decision must be approved or rejected.")
        rejection_route = str(
            payload.get("rejection_route") or "step_4_open_design_translation"
        ).strip()
        if rejection_route not in VALID_REJECTION_ROUTES:
            rejection_route = "step_4_open_design_translation"
        return {
            "stage": "pod_human_review_decision",
            "status": decision,
            "decision": decision,
            "reviewer": str(payload.get("reviewer") or "").strip(),
            "reviewed_at": str(payload.get("reviewed_at") or "").strip() or utc_now(),
            "rejection_route": rejection_route,
            "rejection_reasons": [
                str(item).strip()
                for item in (payload.get("rejection_reasons") or [])
                if str(item).strip()
            ],
            "requested_changes": [
                str(item).strip()
                for item in (payload.get("requested_changes") or [])
                if str(item).strip()
            ],
            "approved_notes": str(payload.get("approved_notes") or "").strip(),
        }
