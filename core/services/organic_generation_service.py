import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from core.campaign.page_campaign_context_loader import PageCampaignContextLoader
from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.notifications.telegram_notifier import TelegramNotifier
from core.prompts.prompt_loader import PromptLoader
from core.services.organic_strategy_service import OrganicStrategyService
from core.services.open_design_visual_translation_service import OpenDesignVisualTranslationService
from core.services.comfyui_preparation_service import ComfyUIPreparationService


class OrganicGenerationService:
    """
    Production organic generation service.

    Final flow:
    Page_Channel_Library
    → Campaign KPI Context
    → Alysha-compliant Organic Strategy Review / Translation
    → Organic Generation prompt
    → Claude generates organic posts without final image prompts
    → Open Design visual translation runs per post and creates visual truth mapped to that exact post text
    → ChatGPT image prompt is written back to each post for GSheet compatibility
    → ComfyUI workflow/config JSON is prepared from the same Open Design visual truth
    → existing GoogleSheetsExporter exports Organic_Posts unchanged
    → Telegram notify
    """

    def __init__(
        self,
        prompt_file: str = "data/prompts/organic/organic_generation_prompt.txt",
    ):
        self.prompt_file = prompt_file
        self.context_loader = PageCampaignContextLoader()
        self.prompt_loader = PromptLoader()
        self.claude = ClaudeAPIAdapter()
        self.exporter = GoogleSheetsExporter()
        self.notifier = TelegramNotifier()
        self.organic_strategy_service = OrganicStrategyService()
        self.open_design_visual_service = OpenDesignVisualTranslationService()
        self.comfyui_preparation_service = ComfyUIPreparationService()

    def _parse_json_response(self, raw: Any) -> Tuple[Dict[str, Any], str]:
        if isinstance(raw, dict):
            for key in ["response", "content", "text", "result", "response_text"]:
                if raw.get(key):
                    raw = raw[key]
                    break

        if hasattr(raw, "content"):
            try:
                raw = "\n".join([block.text for block in raw.content if hasattr(block, "text")])
            except Exception:
                raw = str(raw)

        if not isinstance(raw, str):
            raw = str(raw)

        try:
            return json.loads(raw), raw
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError("Claude organic generation response did not contain valid JSON.")
        return json.loads(match.group()), raw

    def _call_claude(self, prompt: str):
        try:
            return self.claude.run(prompt=prompt, max_tokens=9000, temperature=0.35)
        except TypeError:
            return self.claude.run(prompt=prompt)

    def build_input(self, brand_id: str, page_id: str, platform_id: str):
        context = self.context_loader.load(brand_id, page_id, platform_id)
        page_context = context["page_context"]
        kpi_context = context["campaign_kpi_context"]

        strategy_review = self.organic_strategy_service.review_or_create(
            page_context=page_context,
            campaign_kpi_context=kpi_context,
        )
        organic_strategy_output = strategy_review["strategy_output"]
        recent_learning = strategy_review.get("recent_organic_learning_context") or []

        organic_input = {
            "brand_id": brand_id,
            "niche_id": page_context.get("niche_id"),
            "page_id": page_id,
            "platform_id": platform_id,
            "campaign_id": page_context.get("campaign_id", ""),
            "page_context": page_context,
            "campaign_kpi_context": kpi_context,
            "organic_strategy_output": organic_strategy_output,
            "recent_organic_learning_context": recent_learning,
            "generation_instruction": {
                "must_obey_alysha_source_of_truth": True,
                "must_use_organic_strategy_output": True,
                "must_use_campaign_kpi_context": True,
                "must_use_recent_organic_learning_context_when_available": bool(recent_learning),
                "protected_strategy_fields_must_not_change": organic_strategy_output.get("alysha_compliance", {}).get("protected_alysha_fields", []),
                "allowed_organic_expansion_fields": [
                    "audience slice",
                    "scenario",
                    "hook",
                    "format",
                    "tone",
                    "content archetype",
                    "posting angle",
                    "SEO wording",
                    "reaction trigger",
                ],
                "learning_instruction": (
                    "Use learning only to improve organic execution tactics inside the Alysha-compliant organic strategy. "
                    "Never rewrite Alysha protected strategy truth."
                ),
                "recommended_daily_post_count": kpi_context.get("recommended_daily_post_count"),
                "future_queue_needed": kpi_context.get("future_queue_needed"),
                "content_intensity": kpi_context.get("content_intensity"),
                "kpi_status": kpi_context.get("kpi_status"),
                "instruction": kpi_context.get("generation_instruction"),
                "image_prompt_generation_policy": (
                    "Do not generate final chatgpt_image_prompt in the organic content generation step. "
                    "Provide strong image_intent, content context, and product_reference_note only. "
                    "Open Design visual translation will map the exact post text into final ChatGPT and ComfyUI prompt packages."
                ),
            },
        }
        return organic_input, context, strategy_review

    def run(self, brand_id: str = "AODAI", page_id: str = "AODAI_FB_US", platform_id: str = "facebook"):
        organic_input, context, strategy_review = self.build_input(brand_id, page_id, platform_id)

        prompt = self.prompt_loader.render(
            self.prompt_file,
            {"ORGANIC_INPUT": json.dumps(organic_input, ensure_ascii=False, indent=2)},
        )
        parsed, raw = self._parse_json_response(self._call_claude(prompt))

        output = {
            "organic_run_id": f"ORG_RUN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "brand_id": brand_id,
            "niche_id": context["page_context"].get("niche_id"),
            "page_id": page_id,
            "platform_id": platform_id,
            "campaign_id": context["page_context"].get("campaign_id", ""),
            "page_url": context["page_context"].get("page_url") or context["route"].get("page_url", ""),
            "campaign_kpi_context": context["campaign_kpi_context"],
            "organic_strategy_output_file": strategy_review.get("strategy_output_file"),
            "organic_alysha_source_output_file": strategy_review.get("alysha_source_output_file"),
            "organic_strategy_mode": (strategy_review.get("strategy_output") or {}).get("strategy_mode"),
            "organic_strategy_review_decision": strategy_review.get("review_decision") or {},
            "alysha_source_hash": (
                (strategy_review.get("strategy_output") or {})
                .get("alysha_compliance", {})
                .get("strategy_source_hash")
            ),
            "data": parsed,
            "organic_posts": parsed.get("organic_posts", []),
            "raw_response": raw,
        }

        output_file = Path(strategy_review["organic_output_file"])
        open_design_summary = self.open_design_visual_service.translate_output(
            organic_output=output,
            organic_strategy_output=strategy_review.get("strategy_output") or {},
        )
        comfyui_summary = self.comfyui_preparation_service.prepare_for_output(
            organic_output=output,
            organic_strategy_output=strategy_review.get("strategy_output") or {},
            organic_output_file=output_file,
        )
        output["open_design_visual_translation"] = open_design_summary
        output["comfyui_preparation"] = comfyui_summary

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

        # Keep existing GSheet Organic_Posts export behavior unchanged.
        export_result = self.exporter.export_organic_posts(
            organic_output=output,
            route=context["route"],
            campaign_kpi_context=context["campaign_kpi_context"],
        )

        self.notifier.send(
            "✅ Organic content generated and exported\n"
            f"Brand: {brand_id}\n"
            f"Page: {page_id}\n"
            f"Campaign: {context['page_context'].get('campaign_id', '')}\n"
            f"Organic mode: {output.get('organic_strategy_mode')}\n"
            f"KPI status: {context['campaign_kpi_context'].get('kpi_status')}\n"
            f"Content intensity: {context['campaign_kpi_context'].get('content_intensity')}\n"
            f"Rows appended: {export_result.get('rows_appended')}\n"
            f"Open Design visual packages: {open_design_summary.get('posts_translated', 0)}\n"
            f"ComfyUI workflows prepared: {comfyui_summary.get('workflows_prepared', 0)}\n"
            "Organic strategy review ran before generation; see Telegram update only if strategy changed."
        )

        return {
            "status": "success",
            "output_file": str(output_file),
            "organic_strategy_output_file": strategy_review.get("strategy_output_file"),
            "organic_alysha_source_output_file": strategy_review.get("alysha_source_output_file"),
            "organic_strategy_mode": output.get("organic_strategy_mode"),
            "organic_strategy_review_decision": strategy_review.get("review_decision") or {},
            "open_design_visual_translation": open_design_summary,
            "comfyui_preparation": comfyui_summary,
            "export_result": export_result,
            "campaign_kpi_context": context["campaign_kpi_context"],
        }
