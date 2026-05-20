import copy
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.prompts.prompt_loader import PromptLoader
from core.services.brand_registry_service import BrandRegistryService
from core.services.pod_cache_service import PodLLMOutputCache


class OrganicAlyshaSourceService:
    """
    Builds the upstream Alysha-compliant source strategy used by OrganicStrategyService.

    Why this exists:
    - The global data/output/strategy_output.json may belong to an old paid/event strategy.
    - Organic growth must not inherit expired event language when Page_Channel_Library.notes
      does not request an event.
    - This service creates a page/campaign-scoped Alysha source strategy before the organic
      execution strategy is reviewed.

    Output path:
      data/output/{brand_id}/{page_id}/{campaign_id}/organic_posts/organic_alysha_source_output.json

    Event rule:
    - notes beginning with `event:` => event-aware organic source
    - empty or ordinary notes => evergreen organic growth source
    """

    ALYSHA_REQUIRED_SECTIONS = [
        "campaign_direction_alignment",
        "target_persona",
        "customer_psychology",
        "strategy_map",
        "priority_angles",
        "hook_guidance",
        "core_message",
        "offer_strategy",
        "reason_to_believe",
        "mechanism",
        "voc_summary",
        "creative_mechanics",
        "visual_formats",
        "creative_direction",
        "do_not_do",
    ]

    COMMON_EVENT_MARKERS = [
        "mother's day",
        "mothers day",
        "mothers_day",
        "father's day",
        "fathers day",
        "fathers_day",
        "black friday",
        "cyber monday",
        "christmas",
        "valentine",
        "valentine's day",
        "tet",
        "lunar new year",
        "new year",
        "thanksgiving",
        "halloween",
    ]

    def __init__(
        self,
        prompt_file: str = "data/prompts/organic/organic_alysha_source_prompt.txt",
        reference_strategy_file: str = "data/output/strategy_output.json",
        output_root: Optional[str] = None,
    ):
        self.prompt_file = prompt_file
        self.reference_strategy_file = Path(reference_strategy_file)
        self.output_root = Path(output_root) if output_root else None
        self.registry = BrandRegistryService()
        self.prompt_loader = PromptLoader()
        self.claude = ClaudeAPIAdapter()

    # -------------------------
    # Basic utilities
    # -------------------------
    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _iso_now(self) -> str:
        return self._now_utc().isoformat()

    def _clean_str(self, value: Any) -> str:
        return str(value or "").strip()

    def _safe_component(self, value: Any) -> str:
        raw = self._clean_str(value)
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
        return cleaned or "unknown"

    def _required_identifier(self, page_context: Dict[str, Any], key: str) -> str:
        value = self._clean_str(page_context.get(key))
        if not value:
            raise ValueError(f"Page_Channel_Library is missing required identifier: {key}")
        return value

    def _event_note_from_notes(self, notes: Any) -> str:
        raw = self._clean_str(notes)
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered.startswith("event:"):
            return raw.split(":", 1)[1].strip()
        return ""

    def _source_mode(self, page_context: Dict[str, Any]) -> str:
        return "event_aware" if self._event_note_from_notes(page_context.get("notes")) else "evergreen_growth"

    def _base_output_dir(self, page_context: Dict[str, Any]) -> Path:
        brand_id = self._required_identifier(page_context, "brand_id")
        page_id = self._required_identifier(page_context, "page_id")
        campaign_id = self._required_identifier(page_context, "campaign_id")
        if self.output_root:
            return (
                self.output_root
                / self._safe_component(brand_id)
                / self._safe_component(page_id)
                / self._safe_component(campaign_id)
                / "organic_posts"
            )
        return (
            self.registry.brand_data_root(brand_id)
            / "organic"
            / "pages"
            / self._safe_component(page_id)
            / "campaigns"
            / self._safe_component(campaign_id)
            / "01_alysha_source"
        )

    def source_output_path(self, page_context: Dict[str, Any]) -> Path:
        return self._base_output_dir(page_context) / "organic_alysha_source_output.json"

    def _load_json(self, path: Path, default=None):
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _stable_hash(self, payload: Any) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # -------------------------
    # Input / refresh logic
    # -------------------------
    def _brand_context_source_file(self, page_context: Dict[str, Any]) -> Path:
        brand_id = self._required_identifier(page_context, "brand_id")
        return (
            self.registry.brand_data_root(brand_id)
            / "brand_context"
            / "alysha"
            / "brand_context_source_of_truth.json"
        )

    def _load_reference_strategy(self, page_context: Dict[str, Any]) -> Tuple[Dict[str, Any], Path, str]:
        brand_context_file = self._brand_context_source_file(page_context)
        if brand_context_file.exists():
            return self._load_json(brand_context_file, default={}) or {}, brand_context_file, "brand_context_source_of_truth"
        return self._load_json(self.reference_strategy_file, default={}) or {}, self.reference_strategy_file, "legacy_strategy_output"

    def _strategy_data(self, strategy_output: Dict[str, Any]) -> Dict[str, Any]:
        data = strategy_output.get("data")
        if isinstance(data, dict):
            return data
        brand_context = strategy_output.get("brand_context_source_of_truth")
        if isinstance(brand_context, dict):
            return {
                "campaign_direction_alignment": {
                    "brand_overview": brand_context.get("brand_overview"),
                    "what_makes_them_different": brand_context.get("what_makes_them_different"),
                    "the_alternative_solution": brand_context.get("the_alternative_solution"),
                },
                "target_persona": brand_context.get("core_audiences") or {},
                "customer_psychology": {
                    "core_audiences": brand_context.get("core_audiences") or {},
                    "competitor_landscape": brand_context.get("competitor_landscape") or {},
                    "brand_story_and_origin": brand_context.get("brand_story_and_origin"),
                },
                "strategy_map": {
                    "brand_positioning": brand_context.get("brand_overview"),
                    "differentiators": brand_context.get("what_makes_them_different"),
                    "alternative_solution": brand_context.get("the_alternative_solution"),
                },
                "priority_angles": brand_context.get("content_angles") or brand_context.get("organic_content_angles") or [],
                "hook_guidance": brand_context.get("hook_guidance") or brand_context.get("brand_voice_and_tone") or {},
                "core_message": brand_context.get("core_message") or brand_context.get("brand_overview"),
                "offer_strategy": brand_context.get("offer_strategy") or brand_context.get("product_catalog") or {},
                "reason_to_believe": brand_context.get("reason_to_believe") or brand_context.get("what_makes_them_different"),
                "mechanism": brand_context.get("mechanism") or brand_context.get("product_catalog") or {},
                "voc_summary": brand_context.get("voc_summary") or brand_context.get("brand_voice_and_tone") or {},
                "creative_mechanics": brand_context.get("creative_mechanics") or brand_context.get("creative_constraints") or [],
                "visual_formats": brand_context.get("visual_formats") or brand_context.get("product_catalog") or {},
                "creative_direction": brand_context.get("creative_direction") or brand_context.get("brand_voice_and_tone") or {},
                "do_not_do": brand_context.get("do_not_do") or brand_context.get("creative_constraints") or [],
                "brand_context_source": brand_context,
            }
        return strategy_output

    def _structured_reference(self, reference_strategy: Dict[str, Any]) -> Dict[str, Any]:
        data = self._strategy_data(reference_strategy)
        structured = {}
        for key in self.ALYSHA_REQUIRED_SECTIONS:
            structured[key] = data.get(key, [] if key != "do_not_do" else [])
        if data.get("campaign_direction_used") is not None:
            structured["campaign_direction_used"] = data.get("campaign_direction_used")
        if data.get("strategy_summary") is not None:
            structured["strategy_summary"] = data.get("strategy_summary")
        return structured

    def _reference_event_markers(self, reference_strategy: Dict[str, Any]) -> List[str]:
        blob = json.dumps(reference_strategy, ensure_ascii=False).lower()
        return [marker for marker in self.COMMON_EVENT_MARKERS if marker in blob]

    def _source_input_hash(
        self,
        page_context: Dict[str, Any],
        campaign_kpi_context: Dict[str, Any],
        campaign_direction_context: Optional[Dict[str, Any]],
        structured_reference: Dict[str, Any],
        reference_event_markers: List[str],
    ) -> str:
        stable_input = {
            "identifiers": {
                "brand_id": self._required_identifier(page_context, "brand_id"),
                "niche_id": self._required_identifier(page_context, "niche_id"),
                "page_id": self._required_identifier(page_context, "page_id"),
                "campaign_id": self._required_identifier(page_context, "campaign_id"),
                "platform_id": self._required_identifier(page_context, "platform_id"),
            },
            "notes": self._clean_str(page_context.get("notes")),
            "source_mode": self._source_mode(page_context),
            "event_note": self._event_note_from_notes(page_context.get("notes")),
            "kpi_brief": {
                "start_day": campaign_kpi_context.get("start_day"),
                "end_day": campaign_kpi_context.get("end_day"),
                "target_followers": campaign_kpi_context.get("target_followers"),
                "target_likes": campaign_kpi_context.get("target_likes"),
                "primary_growth_metric": campaign_kpi_context.get("primary_growth_metric"),
            },
            "reference_strategy_hash": self._stable_hash(structured_reference),
            "reference_event_markers": reference_event_markers,
            "campaign_macro_direction": page_context.get("campaign_macro_direction"),
            "campaign_direction_context_hash": self._stable_hash(campaign_direction_context or {}),
        }
        return self._stable_hash(stable_input)

    def _needs_refresh(self, existing: Optional[Dict[str, Any]], source_mode: str, input_hash: str) -> Tuple[bool, str]:
        force = os.getenv("ORGANIC_ALYSHA_SOURCE_FORCE_REFRESH", "false").lower() == "true"
        if force:
            return True, "forced_by_environment"
        if not existing:
            return True, "source_missing"
        if existing.get("source_mode") != source_mode:
            return True, "source_mode_changed"
        previous_hash = (existing.get("source_resolution") or {}).get("input_hash")
        if previous_hash != input_hash:
            return True, "source_inputs_changed"
        return False, "source_current"

    # -------------------------
    # Prompt / response handling
    # -------------------------
    def _parse_json_response(self, raw: Any) -> Dict[str, Any]:
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
            return json.loads(raw)
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError("Organic Alysha source response did not contain valid JSON.")
        return json.loads(match.group())

    def _call_claude(self, prompt: str):
        try:
            return self.claude.run(prompt=prompt, max_tokens=9000, temperature=0.2)
        except TypeError:
            return self.claude.run(prompt=prompt)

    def _build_prompt_input(
        self,
        page_context: Dict[str, Any],
        campaign_kpi_context: Dict[str, Any],
        campaign_direction_context: Optional[Dict[str, Any]],
        source_mode: str,
        structured_reference: Dict[str, Any],
        reference_event_markers: List[str],
    ) -> Dict[str, Any]:
        event_note = self._event_note_from_notes(page_context.get("notes"))
        return {
            "today_utc": self._now_utc().date().isoformat(),
            "identifiers": {
                "brand_id": self._required_identifier(page_context, "brand_id"),
                "niche_id": self._required_identifier(page_context, "niche_id"),
                "page_id": self._required_identifier(page_context, "page_id"),
                "campaign_id": self._required_identifier(page_context, "campaign_id"),
                "platform_id": self._required_identifier(page_context, "platform_id"),
            },
            "page_context": page_context,
            "source_mode": source_mode,
            "event_switch": {
                "notes_value": self._clean_str(page_context.get("notes")),
                "event_note": event_note,
                "event_detection_rule": "Only notes beginning with 'event:' activate event-aware organic source strategy.",
                "evergreen_rule": "Empty or ordinary notes must produce an evergreen organic growth strategy with no expired event urgency.",
            },
            "campaign_kpi_context": campaign_kpi_context,
            "campaign_direction_context": campaign_direction_context or {},
            "reference_alysha_strategy": structured_reference,
            "reference_event_markers_to_remove_when_evergreen": reference_event_markers,
            "required_alysha_sections": list(self.ALYSHA_REQUIRED_SECTIONS),
        }

    # -------------------------
    # Validation / assembly
    # -------------------------
    def _validate_sections(self, parsed: Dict[str, Any], source_mode: str, reference_event_markers: List[str]) -> None:
        missing = []
        for key in self.ALYSHA_REQUIRED_SECTIONS:
            value = parsed.get(key)
            if value is None or value == [] or value == {} or value == "":
                missing.append(key)
        if missing:
            raise ValueError(f"Organic Alysha source is missing required sections: {missing}")

        if source_mode == "evergreen_growth" and reference_event_markers:
            blob = json.dumps(parsed, ensure_ascii=False).lower()
            leaked = [marker for marker in reference_event_markers if marker in blob]
            if leaked:
                raise ValueError(
                    "Evergreen organic Alysha source still contains reference event language: "
                    f"{leaked}. Regenerate the source before creating organic posts."
                )

    def usage_summary(self, reset=False):
        return self.claude.usage_summary(reset=reset)

    def _cache_input_for_reusable_source(self, prompt_input: Dict[str, Any]) -> Dict[str, Any]:
        """Build a cache key that safely reuses equivalent Alysha organic source calls.

        campaign_id is an execution identifier, not a strategic signal. Removing it from
        the cache key allows multiple campaigns with otherwise identical source inputs to
        reuse the same Claude result instead of paying for an equivalent regeneration.
        Any strategic difference (direction library record, KPI brief, notes, macro direction,
        page context values, reference strategy hash) remains in the key.
        """
        cacheable = copy.deepcopy(prompt_input or {})
        identifiers = cacheable.get("identifiers") or {}
        identifiers.pop("campaign_id", None)
        page_context = cacheable.get("page_context") or {}
        page_context.pop("campaign_id", None)
        return cacheable

    def resolve(
        self,
        page_context: Dict[str, Any],
        campaign_kpi_context: Dict[str, Any],
        campaign_direction_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        output_path = self.source_output_path(page_context)
        existing = self._load_json(output_path, default=None)
        reference_strategy, reference_strategy_file, reference_source_type = self._load_reference_strategy(page_context)
        structured_reference = self._structured_reference(reference_strategy)
        reference_event_markers = self._reference_event_markers(structured_reference)
        source_mode = self._source_mode(page_context)
        input_hash = self._source_input_hash(
            page_context=page_context,
            campaign_kpi_context=campaign_kpi_context,
            campaign_direction_context=campaign_direction_context,
            structured_reference=structured_reference,
            reference_event_markers=reference_event_markers,
        )
        refresh, refresh_reason = self._needs_refresh(existing, source_mode, input_hash)

        if not refresh:
            return {
                "source_output": existing,
                "source_output_file": str(output_path),
                "source_refreshed": False,
                "source_refresh_reason": refresh_reason,
            }

        readiness = self.claude.readiness()
        if not readiness.get("ready"):
            if existing:
                return {
                    "source_output": existing,
                    "source_output_file": str(output_path),
                    "source_refreshed": False,
                    "source_refresh_reason": "claude_not_ready_reused_existing_source",
                }
            raise RuntimeError(
                "Organic Alysha source strategy requires Claude for first generation, but Claude is not ready."
            )

        prompt_input = self._build_prompt_input(
            page_context=page_context,
            campaign_kpi_context=campaign_kpi_context,
            campaign_direction_context=campaign_direction_context,
            source_mode=source_mode,
            structured_reference=structured_reference,
            reference_event_markers=reference_event_markers,
        )
        prompt = self.prompt_loader.render(
            self.prompt_file,
            {"ORGANIC_ALYSHA_SOURCE_INPUT": json.dumps(prompt_input, ensure_ascii=False, indent=2)},
        )
        brand_id = self._required_identifier(page_context, "brand_id")
        cache = PodLLMOutputCache(brand_id=brand_id, namespace="organic_alysha_source")
        cache_input = {
            "prompt_file": self.prompt_file,
            "prompt_input": self._cache_input_for_reusable_source(prompt_input),
        }
        cache_hash = cache.input_hash(cache_input)
        cached = cache.get(cache_hash)
        if cached:
            parsed = (cached.get("output") or {}).get("parsed") or {}
            source_cache_status = "hit"
        else:
            parsed = self._parse_json_response(self._call_claude(prompt))
            cache.set(
                input_hash=cache_hash,
                output={"parsed": parsed},
                api_meta={"provider": "claude", "stage": "organic_alysha_source"},
                cache_input=cache_input,
            )
            source_cache_status = "stored"
        self._validate_sections(parsed, source_mode=source_mode, reference_event_markers=reference_event_markers)

        event_note = self._event_note_from_notes(page_context.get("notes"))
        output = {
            "stage": "organic_alysha_strategy_source",
            "status": "ready",
            "generated_at": self._iso_now(),
            "source_mode": source_mode,
            "event_context": {
                "event_note": event_note,
                "notes_value": self._clean_str(page_context.get("notes")),
                "event_detection_rule": "Only notes beginning with 'event:' activate event-aware organic source strategy.",
            },
            "identifiers": {
                "brand_id": self._required_identifier(page_context, "brand_id"),
                "niche_id": self._required_identifier(page_context, "niche_id"),
                "page_id": self._required_identifier(page_context, "page_id"),
                "campaign_id": self._required_identifier(page_context, "campaign_id"),
                "platform_id": self._required_identifier(page_context, "platform_id"),
            },
            "source_resolution": {
                "input_hash": input_hash,
                "refresh_reason": refresh_reason,
                "reference_strategy_file": str(reference_strategy_file),
                "reference_source_type": reference_source_type,
                "reference_strategy_hash": self._stable_hash(structured_reference),
                "reference_event_markers": reference_event_markers,
                "campaign_direction_context": campaign_direction_context or {},
                "cache_status": source_cache_status,
                "cache_hash": cache_hash,
            },
            "data": parsed,
        }
        self._write_json(output_path, output)
        return {
            "source_output": output,
            "source_output_file": str(output_path),
            "source_refreshed": True,
            "source_refresh_reason": refresh_reason,
        }
