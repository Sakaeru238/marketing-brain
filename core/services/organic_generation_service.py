import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from core.campaign.page_campaign_context_loader import PageCampaignContextLoader
from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.notifications.telegram_notifier import TelegramNotifier
from core.prompts.prompt_loader import PromptLoader
from core.services.brand_registry_service import BrandRegistryService
from core.services.organic_strategy_service import OrganicStrategyService
from core.services.pod_cache_service import PodLLMOutputCache, stable_hash
from core.services.open_design_visual_translation_service import OpenDesignVisualTranslationService
from core.services.comfyui_preparation_service import ComfyUIPreparationService
from core.schedulers.behavioral_schedule_engine import BehavioralScheduleEngine


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
        self.registry = BrandRegistryService()
        self.organic_strategy_service = OrganicStrategyService()
        self.open_design_visual_service = OpenDesignVisualTranslationService()
        self.comfyui_preparation_service = ComfyUIPreparationService()
        self.schedule_engine = BehavioralScheduleEngine()

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

    REQUIRED_POST_FIELDS = [
        "planned_publish_day", "platform_id", "content_archetype",
        "interaction_trigger_type", "target_human", "current_emotional_state",
        "core_problem", "core_solution", "primary_takeaway", "desired_post_outcome",
        "desired_action", "awareness_stage", "post_format", "content_role",
        "content_pillar", "angle_used", "hook_type", "product_mention_level",
        "hook", "post_text", "engagement_prompt", "content_tags", "seo_keywords_used",
        "brand_keywords_used", "trend_keywords_used", "platform_native_keywords",
        "reaction_prediction", "image_intent", "product_reference_required",
        "product_reference_note", "image_url", "recommended_posting_window",
        "behavioral_reason", "historical_confidence", "scheduled_datetime_utc",
        "campaign_kpi_influence",
    ]

    def _collect_organic_generation_validation_errors(
        self,
        parsed: Dict[str, Any],
        organic_input: Dict[str, Any],
    ) -> List[str]:
        errors: List[str] = []
        if not isinstance(parsed, dict):
            return ["Organic generation output must be a JSON object."]

        posts = parsed.get("organic_posts")
        if not isinstance(posts, list):
            return ["Organic generation output must contain organic_posts as a list."]

        exact_count = int(
            ((organic_input.get("campaign_kpi_context") or {}).get("posting_frequency_target_count") or 1)
        )
        if len(posts) != exact_count:
            errors.append(
                "Organic generation output post count mismatch: "
                f"expected {exact_count} from posting_frequency_target, got {len(posts)}."
            )

        for idx, post in enumerate(posts, start=1):
            if not isinstance(post, dict):
                errors.append(f"Organic post #{idx} must be an object.")
                continue

            missing = [field for field in self.REQUIRED_POST_FIELDS if field not in post]
            if missing:
                errors.append(f"Organic post #{idx} is missing required fields: {missing}")

            for field in ["hook", "post_text", "engagement_prompt", "image_intent"]:
                if not str(post.get(field) or "").strip():
                    errors.append(f"Organic post #{idx} has an empty required content field: {field}")

            kpi = post.get("campaign_kpi_influence") or {}
            if not isinstance(kpi, dict):
                errors.append(f"Organic post #{idx} campaign_kpi_influence must be an object.")
                continue
            kpi_missing = [
                field
                for field in ["kpi_status", "content_intensity", "why_this_post_fits_kpi"]
                if not str(kpi.get(field) or "").strip()
            ]
            if kpi_missing:
                errors.append(
                    f"Organic post #{idx} campaign_kpi_influence is missing or empty: {kpi_missing}"
                )

        return errors

    def _validate_organic_generation_output(self, parsed: Dict[str, Any], organic_input: Dict[str, Any]) -> None:
        errors = self._collect_organic_generation_validation_errors(parsed, organic_input)
        if errors:
            raise ValueError("Organic generation validation failed: " + " | ".join(errors))

    def _safe_id_component(self, value: Any, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "")).strip("_").upper()
        return cleaned or fallback

    def _assign_system_post_ids(self, parsed: Dict[str, Any], organic_input: Dict[str, Any]) -> None:
        posts = parsed.get("organic_posts") or []
        brand_component = self._safe_id_component(organic_input.get("brand_id"), "BRAND")
        campaign_component = self._safe_id_component(organic_input.get("campaign_id"), "CAMPAIGN")
        batch_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        for idx, post in enumerate(posts, start=1):
            if isinstance(post, dict):
                post["post_id"] = f"ORG_{brand_component}_{campaign_component}_{batch_stamp}_{idx:02d}"

    def _build_validation_repair_prompt(
        self,
        original_prompt: str,
        parsed: Dict[str, Any],
        errors: List[str],
        organic_input: Dict[str, Any],
    ) -> str:
        exact_count = int(
            ((organic_input.get("campaign_kpi_context") or {}).get("posting_frequency_target_count") or 1)
        )
        error_lines = "\n".join(f"- {error}" for error in errors)
        previous_output = json.dumps(parsed, ensure_ascii=False, indent=2)
        return (
            f"{original_prompt}\n\n"
            "SYSTEM VALIDATION REPAIR TASK:\n"
            "The previous JSON response failed the internal Organic Post Validator. "
            "Return one corrected JSON object only. No markdown. No commentary.\n"
            f"The corrected output must contain exactly {exact_count} organic_posts item(s).\n"
            "Every organic_posts item must be a JSON object.\n"
            "Do not output post_id; Python assigns post_id after validation.\n"
            "Do not leave hook, post_text, engagement_prompt, image_intent, or campaign_kpi_influence fields empty.\n"
            "campaign_kpi_influence must contain non-empty kpi_status, content_intensity, and why_this_post_fits_kpi.\n"
            "Fix every validator error below while preserving the strategic intent whenever possible:\n"
            f"{error_lines}\n\n"
            "Previous invalid JSON response:\n"
            f"{previous_output}"
        )

    def _existing_scheduled_timestamps(self, route: Dict[str, Any]) -> Set[str]:
        try:
            spreadsheet = self.exporter._open_spreadsheet_for_route(route)
            tab = self.exporter._tab_name(route, "posts", "Organic_Posts")
            ws = spreadsheet.worksheet(tab)
            records = self.exporter._worksheet_records(ws)
        except Exception:
            return set()
        return {
            str(row.get("scheduled_datetime_utc") or "").strip()
            for row in records
            if str(row.get("scheduled_datetime_utc") or "").strip()
        }

    def _window_candidate_datetimes(self, day_value: str, window: str, timezone_name: str) -> List[datetime]:
        try:
            local_day = datetime.fromisoformat(str(day_value)).date()
        except Exception:
            local_day = datetime.now(ZoneInfo(timezone_name)).date() + timedelta(days=1)
        start_raw, end_raw = self.schedule_engine.FALLBACK_WINDOWS.get(
            window,
            self.schedule_engine.FALLBACK_WINDOWS["evening_scroll"],
        )
        start_hour, start_minute = [int(part) for part in start_raw.split(":")]
        end_hour, end_minute = [int(part) for part in end_raw.split(":")]
        tz = ZoneInfo(timezone_name)
        start_dt = datetime(local_day.year, local_day.month, local_day.day, start_hour, start_minute, tzinfo=tz)
        end_dt = datetime(local_day.year, local_day.month, local_day.day, end_hour, end_minute, tzinfo=tz)
        candidates = []
        cursor = start_dt
        while cursor <= end_dt:
            candidates.append(cursor)
            cursor += timedelta(minutes=15)
        if not candidates:
            candidates = [start_dt]
        midpoint = len(candidates) // 2
        ordered = [candidates[midpoint]]
        for offset in range(1, len(candidates)):
            left = midpoint - offset
            right = midpoint + offset
            if left >= 0:
                ordered.append(candidates[left])
            if right < len(candidates):
                ordered.append(candidates[right])
        return ordered

    def _resolve_schedule_conflicts(self, posts: List[Dict[str, Any]], route: Dict[str, Any], page_context: Dict[str, Any]) -> Dict[str, Any]:
        occupied = self._existing_scheduled_timestamps(route)
        assigned = []
        timezone_name = str(page_context.get("target_timezone") or "UTC").strip() or "UTC"
        adjustments = []
        for post in posts:
            desired = str(post.get("scheduled_datetime_utc") or "").strip()
            if desired and desired not in occupied:
                occupied.add(desired)
                assigned.append(desired)
                continue
            window = str(post.get("recommended_posting_window") or "evening_scroll").strip() or "evening_scroll"
            planned_day = str(post.get("planned_publish_day") or "").strip()
            selected_utc = ""
            selected_local = None
            for local_dt in self._window_candidate_datetimes(planned_day, window, timezone_name):
                utc_text = local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if utc_text not in occupied:
                    selected_utc = utc_text
                    selected_local = local_dt
                    break
            if not selected_utc:
                # Exhausted the preferred window; use a 15-minute tail after the last fallback window.
                fallback_candidates = self._window_candidate_datetimes(planned_day, "evening_scroll", timezone_name)
                tail = fallback_candidates[-1] if fallback_candidates else datetime.now(ZoneInfo(timezone_name))
                while True:
                    tail += timedelta(minutes=15)
                    utc_text = tail.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if utc_text not in occupied:
                        selected_utc = utc_text
                        selected_local = tail
                        break
            previous = desired
            post["scheduled_datetime_utc"] = selected_utc
            if selected_local is not None:
                post["scheduled_date_local"] = selected_local.date().isoformat()
                post["scheduled_time_local"] = selected_local.strftime("%H:%M")
                post["scheduled_datetime_local"] = selected_local.strftime("%Y-%m-%dT%H:%M:%S")
            post["behavioral_reason"] = (
                str(post.get("behavioral_reason") or "").strip()
                + " | Cross-campaign schedule allocator kept the post inside the preferred behavioral window when possible and avoided an occupied posting timestamp."
            ).strip(" |")
            occupied.add(selected_utc)
            assigned.append(selected_utc)
            adjustments.append({"post_id": post.get("post_id"), "from": previous, "to": selected_utc, "window": window})
        return {"assigned_timestamps": assigned, "adjustments": adjustments, "adjusted_count": len(adjustments)}

    def usage_summary(self, reset=False):
        own = self.claude.usage_summary(reset=reset)
        strategy = self.organic_strategy_service.usage_summary(reset=reset)
        visual = self.open_design_visual_service.usage_summary(reset=reset)
        return {
            "calls": own.get("calls", 0) + strategy.get("calls", 0) + visual.get("calls", 0),
            "input_tokens": own.get("input_tokens", 0) + strategy.get("input_tokens", 0) + visual.get("input_tokens", 0),
            "output_tokens": own.get("output_tokens", 0) + strategy.get("output_tokens", 0) + visual.get("output_tokens", 0),
            "total_tokens": own.get("total_tokens", 0) + strategy.get("total_tokens", 0) + visual.get("total_tokens", 0),
            "total_cost_usd": round(float(own.get("total_cost_usd", 0.0)) + float(strategy.get("total_cost_usd", 0.0)) + float(visual.get("total_cost_usd", 0.0)), 8),
            "organic_generation": own,
            "organic_strategy_and_source": strategy,
            "open_design_visual_translation": visual,
        }

    def _write_source_snapshot(
        self,
        *,
        brand_id: str,
        page_id: str,
        platform_id: str,
        campaign_id: str,
        context: Dict[str, Any],
        strategy_review: Dict[str, Any],
    ) -> str:
        brand_root = self.registry.brand_data_root(brand_id)
        campaign_root = (
            brand_root
            / "organic"
            / "pages"
            / self.organic_strategy_service._safe_component(page_id)
            / "campaigns"
            / self.organic_strategy_service._safe_component(campaign_id)
        )
        input_dir = campaign_root / "00_inputs"
        input_dir.mkdir(parents=True, exist_ok=True)

        brand_context_file = brand_root / "brand_context" / "alysha" / "brand_context_source_of_truth.json"
        brand_context = {}
        if brand_context_file.exists():
            brand_context = json.loads(brand_context_file.read_text(encoding="utf-8"))

        snapshot = {
            "snapshot_type": "organic_campaign_source_snapshot",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "identifiers": {
                "brand_id": brand_id,
                "page_id": page_id,
                "platform_id": platform_id,
                "campaign_id": campaign_id,
            },
            "source_files": {
                "brand_context_file": str(brand_context_file) if brand_context_file.exists() else "",
                "organic_alysha_source_output_file": strategy_review.get("alysha_source_output_file", ""),
                "organic_strategy_output_file": strategy_review.get("strategy_output_file", ""),
            },
            "source_rows": {
                "page_context": context.get("page_context") or {},
                "campaign_kpi_context": context.get("campaign_kpi_context") or {},
            },
            "fingerprints": {
                "brand_context_hash": stable_hash(brand_context),
                "page_context_hash": stable_hash(context.get("page_context") or {}),
                "campaign_kpi_context_hash": stable_hash(context.get("campaign_kpi_context") or {}),
                "organic_strategy_hash": stable_hash(strategy_review.get("strategy_output") or {}),
            },
        }
        snapshot["fingerprints"]["organic_source_hash"] = stable_hash(snapshot["fingerprints"])

        snapshot_file = input_dir / "source_snapshot.json"
        snapshot_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(snapshot_file)

    def _generation_cache_input(self, organic_input: Dict[str, Any]) -> Dict[str, Any]:
        strategy = organic_input.get("organic_strategy_output") or {}
        return {
            "prompt_file": self.prompt_file,
            "brand_id": organic_input.get("brand_id"),
            "niche_id": organic_input.get("niche_id"),
            "page_id": organic_input.get("page_id"),
            "platform_id": organic_input.get("platform_id"),
            "campaign_id": organic_input.get("campaign_id"),
            "page_context": organic_input.get("page_context") or {},
            "campaign_kpi_context": organic_input.get("campaign_kpi_context") or {},
            "campaign_direction_context": organic_input.get("campaign_direction_context") or {},
            "strategy_hash_inputs": {
                "strategy_mode": strategy.get("strategy_mode"),
                "event_context": strategy.get("event_context") or {},
                "alysha_strategy_source_hash": (
                    (strategy.get("alysha_compliance") or {}).get("strategy_source_hash")
                ),
                "organic_execution_strategy": strategy.get("organic_execution_strategy") or {},
                "daily_learning_adjustments": strategy.get("daily_learning_adjustments") or {},
            },
            "recent_organic_learning_context": organic_input.get("recent_organic_learning_context") or [],
            "generation_instruction": organic_input.get("generation_instruction") or {},
        }

    def build_input(self, brand_id: str, page_id: str, platform_id: str, campaign_id: str = None):
        context = self.context_loader.load(brand_id, page_id, platform_id, campaign_id=campaign_id)
        page_context = context["page_context"]
        kpi_context = context["campaign_kpi_context"]

        campaign_direction_context = context.get("campaign_direction_context") or {}
        strategy_review = self.organic_strategy_service.review_or_create(
            page_context=page_context,
            campaign_kpi_context=kpi_context,
            campaign_direction_context=campaign_direction_context,
        )
        organic_strategy_output = strategy_review["strategy_output"]
        recent_learning = strategy_review.get("recent_organic_learning_context") or []

        organic_input = {
            "brand_id": brand_id,
            "niche_id": page_context.get("niche_id"),
            "page_id": page_id,
            "platform_id": platform_id,
            "campaign_id": page_context.get("campaign_id", "") or campaign_id or "",
            "page_context": page_context,
            "campaign_kpi_context": kpi_context,
            "campaign_direction_context": campaign_direction_context,
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
                "exact_post_count_from_posting_frequency_target": kpi_context.get("posting_frequency_target_count"),
                "posting_frequency_target_raw": kpi_context.get("posting_frequency_target"),
                "recommended_daily_post_count_for_pressure_only": kpi_context.get("recommended_daily_post_count"),
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

    def run(self, brand_id: str = "AODAI", page_id: str = "AODAI_FB_US", platform_id: str = "facebook", campaign_id: str = None):
        organic_input, context, strategy_review = self.build_input(brand_id, page_id, platform_id, campaign_id)
        resolved_campaign_id = organic_input.get("campaign_id") or ""
        source_snapshot_file = self._write_source_snapshot(
            brand_id=brand_id,
            page_id=page_id,
            platform_id=platform_id,
            campaign_id=resolved_campaign_id,
            context=context,
            strategy_review=strategy_review,
        )

        cache = PodLLMOutputCache(brand_id=brand_id, namespace="organic_generation")
        cache_input = self._generation_cache_input(organic_input)
        input_hash = cache.input_hash(cache_input)
        prompt = self.prompt_loader.render(
            self.prompt_file,
            {"ORGANIC_INPUT": json.dumps(organic_input, ensure_ascii=False, indent=2)},
        )
        cached = cache.get(input_hash)
        parsed = None
        raw = ""
        initial_validation_errors: List[str] = []
        validation_repair_attempted = False
        cache_invalidated = False

        if cached:
            cached_output = cached.get("output") or {}
            cached_parsed = cached_output.get("parsed") or {}
            cached_raw = cached_output.get("raw_response") or json.dumps(cached_parsed, ensure_ascii=False)
            initial_validation_errors = self._collect_organic_generation_validation_errors(cached_parsed, organic_input)
            if not initial_validation_errors:
                parsed = cached_parsed
                raw = cached_raw
                generation_cache_status = "hit"
            else:
                cache_invalidated = True
                generation_cache_status = "invalidated"
        else:
            generation_cache_status = "miss"

        if parsed is None:
            parsed, raw = self._parse_json_response(self._call_claude(prompt))
            initial_validation_errors = self._collect_organic_generation_validation_errors(parsed, organic_input)
            if initial_validation_errors:
                validation_repair_attempted = True
                repair_prompt = self._build_validation_repair_prompt(
                    prompt,
                    parsed,
                    initial_validation_errors,
                    organic_input,
                )
                parsed, raw = self._parse_json_response(self._call_claude(repair_prompt))

            self._validate_organic_generation_output(parsed, organic_input)
            cache.set(
                input_hash=input_hash,
                output={"parsed": parsed, "raw_response": raw},
                api_meta={
                    "provider": "claude",
                    "stage": "organic_generation",
                    "validator_repair_attempted": validation_repair_attempted,
                },
                cache_input=cache_input,
            )
            generation_cache_status = "repaired_stored" if validation_repair_attempted else "stored"
        else:
            self._validate_organic_generation_output(parsed, organic_input)

        # post_id is a technical identifier; Python assigns it after content validation.
        self._assign_system_post_ids(parsed, organic_input)

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
            "source_snapshot_file": source_snapshot_file,
            "organic_generation_cache": {
                "status": generation_cache_status,
                "input_hash": input_hash,
                "namespace": "organic_generation",
            },
            "organic_generation_validation": {
                "status": "pass",
                "cache_invalidated_before_regeneration": cache_invalidated,
                "repair_attempted": validation_repair_attempted,
                "initial_validation_errors": initial_validation_errors,
                "post_id_assignment": "python_system_generated_after_validation",
            },
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

        schedule_allocation = self._resolve_schedule_conflicts(
            output.get("organic_posts") or [],
            context["route"],
            context["page_context"],
        )
        output["cross_campaign_schedule_allocation"] = schedule_allocation

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

        usage = self.usage_summary(reset=False)

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
            f"Validator repair attempted: {validation_repair_attempted}\n"
            f"Claude tokens: {usage.get('total_tokens', 0)} (in {usage.get('input_tokens', 0)} / out {usage.get('output_tokens', 0)})\n"
            f"Claude cost: ${float(usage.get('total_cost_usd', 0.0)):.6f}\n"
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
            "campaign_direction_context": context.get("campaign_direction_context") or {},
            "cross_campaign_schedule_allocation": schedule_allocation,
            "llm_usage": usage,
        }
