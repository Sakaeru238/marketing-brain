from __future__ import annotations

from typing import Any

from core.services.pod_cache_service import PodLLMOutputCache
from .pod_llm_client import PodClaudeJsonClient
from .pod_prompts import STRATEGY_SYSTEM_PROMPT, build_pod_strategy_prompt


STEP_NAME = "01_alysha_creative_strategy_engine"
PROMPT_VERSION = "pod_strategy_v001"


class PodStrategyService:
    def __init__(self, llm_client: PodClaudeJsonClient) -> None:
        self.llm_client = llm_client

    def run(
        self,
        *,
        brand_context: dict[str, Any],
        brand_learning: dict[str, Any] | None,
        campaign_intake: dict[str, Any],
        product_catalog_entry: dict[str, Any],
        brand_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt = build_pod_strategy_prompt(
            brand_context=brand_context,
            brand_learning=brand_learning,
            campaign_intake=campaign_intake,
            product_catalog_entry=product_catalog_entry,
        )
        cache = None
        input_hash = ""
        if brand_id:
            cache = PodLLMOutputCache(brand_id=brand_id, namespace="step_1_strategy")
            cache_input = {
                "prompt_version": PROMPT_VERSION,
                "model": self.llm_client.model,
                "system": STRATEGY_SYSTEM_PROMPT,
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
            system=STRATEGY_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=12000,
            temperature=0.2,
            metadata={"job": "pod_strategy"},
        )
        if cache:
            cache_file = cache.set(
                input_hash=input_hash,
                output=output,
                api_meta=meta,
                cache_input={
                    "prompt_version": PROMPT_VERSION,
                    "model": self.llm_client.model,
                },
            )
            meta = {**meta, "cache_status": "miss_stored", "cache_file": str(cache_file), "input_hash": input_hash}
        return output, meta
