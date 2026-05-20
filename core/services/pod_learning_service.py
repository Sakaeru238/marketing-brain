from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.services.brand_learning_store import BrandLearningStore
from core.services.brand_learning_summary_service import BrandLearningSummaryService
from .pod_llm_client import PodClaudeJsonClient
from .pod_prompts import POD_LEARNING_SYSTEM_PROMPT, build_pod_learning_prompt
from .pod_pipeline_utils import utc_now, write_json


STEP_NAME = "08_brand_learning_pod_learning"


class PodLearningService:
    def __init__(self, llm_client: PodClaudeJsonClient) -> None:
        self.llm_client = llm_client

    def build_learning(
        self,
        *,
        brand_id: str,
        campaign_id: str,
        strategy_output: dict[str, Any],
        design_brief: dict[str, Any],
        translation_output: dict[str, Any],
        render_result: dict[str, Any],
        visual_eval_result: dict[str, Any],
        human_review_result: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt = build_pod_learning_prompt(
            brand_id=brand_id,
            campaign_id=campaign_id,
            strategy_output=strategy_output,
            design_brief=design_brief,
            translation_output=translation_output,
            render_result=render_result,
            visual_eval_result=visual_eval_result,
            human_review_result=human_review_result,
        )
        return self.llm_client.generate_json(
            step=STEP_NAME,
            system=POD_LEARNING_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=8000,
            temperature=0.1,
            metadata={"job": "pod_learning"},
        )

    def persist_learning(
        self,
        *,
        brand_id: str,
        campaign_id: str,
        learning_output: dict[str, Any],
        output_dir: str | Path,
    ) -> dict[str, Any]:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        pod_learning_file = output_root / "pod_learning_log.jsonl"
        appended_pod_records = []
        for item in learning_output.get("pod_learning") or []:
            record = {
                "brand_id": brand_id,
                "campaign_id": campaign_id,
                "source_type": "pod_pipeline",
                "learning_category": item.get("learning_category") or "pod_execution",
                "learning": item.get("learning") or "",
                "confidence": item.get("confidence") or "medium",
                "recommended_action": item.get("recommended_action") or "",
                "evidence": item.get("evidence") or [],
                "created_at": utc_now(),
            }
            if record["learning"]:
                with pod_learning_file.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                appended_pod_records.append(record)

        store = BrandLearningStore(brand_id=brand_id)
        appended_brand_records = []
        for item in learning_output.get("brand_learning") or []:
            learning = str(item.get("learning") or "").strip()
            if not learning:
                continue
            appended_brand_records.append(
                store.append_learning(
                    source_type="pod_pipeline",
                    learning=learning,
                    learning_category=item.get("learning_category") or "visual_design",
                    confidence=item.get("confidence") or "medium",
                    recommended_action=item.get("recommended_action") or "",
                    evidence=item.get("evidence") or [],
                    source_ref={"campaign_id": campaign_id},
                    learning_scope="pod",
                    metadata={
                        "pod_learning_stage": learning_output.get("stage"),
                        "future_strategy_implications": learning_output.get("future_strategy_implications") or [],
                        "future_design_brief_implications": learning_output.get("future_design_brief_implications") or [],
                        "future_render_prompt_implications": learning_output.get("future_render_prompt_implications") or [],
                    },
                )
            )

        summary = BrandLearningSummaryService(brand_id=brand_id, store=store).rebuild_summary()
        manifest = {
            "stage": "pod_learning_persist",
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "status": "success",
            "created_at": utc_now(),
            "pod_learning_file": str(pod_learning_file),
            "pod_records_appended": len(appended_pod_records),
            "brand_records_appended": len(appended_brand_records),
            "brand_learning_summary_stats": summary.get("stats") or {},
        }
        write_json(output_root / "pod_learning_persist_manifest.json", manifest)
        return manifest
