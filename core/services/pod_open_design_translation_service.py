from __future__ import annotations

from typing import Any

from .pod_llm_client import PodClaudeJsonClient
from .pod_prompts import TRANSLATION_SYSTEM_PROMPT, build_pod_translation_prompt


STEP_NAME = "04_open_design_generative_media_translation"


class PodOpenDesignTranslationService:
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
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt = build_pod_translation_prompt(
            brand_id=brand_id,
            campaign_id=campaign_id,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            strategy_output=strategy_output,
            design_brief=design_brief,
        )
        return self.llm_client.generate_json(
            step=STEP_NAME,
            system=TRANSLATION_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=16000,
            temperature=0.2,
            metadata={"job": "pod_open_design_translation"},
        )
