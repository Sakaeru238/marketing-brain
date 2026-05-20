from __future__ import annotations

from typing import Any

from core.services.pod_cache_service import PodLLMOutputCache
from .pod_llm_client import PodClaudeJsonClient
from .pod_prompts import BRIEF_SYSTEM_PROMPT, build_pod_design_brief_prompt


STEP_NAME = "02_designer_skills_design_brief"
PROMPT_VERSION = "pod_design_brief_v001"


class PodDesignBriefService:
    def __init__(self, llm_client: PodClaudeJsonClient) -> None:
        self.llm_client = llm_client

    def run(
        self,
        *,
        brand_context: dict[str, Any],
        campaign_intake: dict[str, Any],
        product_catalog_entry: dict[str, Any],
        strategy_output: dict[str, Any],
        revision_feedback: dict[str, Any] | None = None,
        brand_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt = build_pod_design_brief_prompt(
            brand_context=brand_context,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
            strategy_output=strategy_output,
            revision_feedback=revision_feedback,
        )
        cache = None
        input_hash = ""
        if brand_id:
            cache = PodLLMOutputCache(brand_id=brand_id, namespace="step_2_design_brief")
            cache_input = {
                "prompt_version": PROMPT_VERSION,
                "model": self.llm_client.model,
                "system": BRIEF_SYSTEM_PROMPT,
                "user": prompt,
            }
            input_hash = cache.input_hash(cache_input)
            cached = cache.get(input_hash)
            if cached:
                return cached["output"], {
                    **cached.get("api_meta", {}),
                    "cache_status": "hit",
                    "cache_file": cached["cache_file"],
                    "input_hash": input_hash,
                }

        output, meta = self.llm_client.generate_json(
            step=STEP_NAME,
            system=BRIEF_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=16000,
            temperature=0.2,
            metadata={"job": "pod_design_brief", "is_revision": bool(revision_feedback)},
        )
        if cache:
            cache_file = cache.set(
                input_hash=input_hash,
                output=output,
                api_meta=meta,
                cache_input={
                    "prompt_version": PROMPT_VERSION,
                    "model": self.llm_client.model,
                    "is_revision": bool(revision_feedback),
                },
            )
            meta = {**meta, "cache_status": "miss_stored", "cache_file": str(cache_file), "input_hash": input_hash}
        return output, meta
