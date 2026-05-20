from __future__ import annotations

from typing import Any

from .pod_llm_client import PodClaudeJsonClient
from .pod_prompts import (
    VISUAL_REGENERATION_SYSTEM_PROMPT,
    build_pod_visual_regeneration_prompt,
)


STEP_NAME = "06b_central_orchestrator_visual_regeneration_instruction"


class PodVisualRegenerationService:
    def __init__(self, llm_client: PodClaudeJsonClient) -> None:
        self.llm_client = llm_client

    def run(
        self,
        *,
        brand_id: str,
        campaign_id: str,
        campaign_intake: dict[str, Any],
        product_catalog_entry: dict[str, Any],
        strategy_output: dict[str, Any],
        design_brief: dict[str, Any],
        translation_output: dict[str, Any],
        render_result: dict[str, Any],
        visual_eval_result: dict[str, Any] | None = None,
        human_review_result: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt = build_pod_visual_regeneration_prompt(
            brand_id=brand_id,
            campaign_id=campaign_id,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            strategy_output=strategy_output,
            design_brief=design_brief,
            translation_output=translation_output,
            render_result=render_result,
            visual_eval_result=visual_eval_result,
            human_review_result=human_review_result,
        )
        return self.llm_client.generate_json(
            step=STEP_NAME,
            system=VISUAL_REGENERATION_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=8000,
            temperature=0.1,
            metadata={"job": "pod_visual_regeneration_instruction"},
        )
