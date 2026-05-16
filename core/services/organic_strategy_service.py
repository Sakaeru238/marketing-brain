import copy
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.engines.claude_api_adapter import ClaudeAPIAdapter
from core.services.organic_alysha_source_service import OrganicAlyshaSourceService
from core.learning.organic_learning_memory_store import OrganicLearningMemoryStore
from core.notifications.telegram_notifier import TelegramNotifier
from core.prompts.prompt_loader import PromptLoader


class OrganicStrategyService:
    """
    Produces and reviews an Alysha-compliant organic execution strategy.

    This service does NOT invent a new master strategy. It translates the current
    Alysha Strategy Output into an organic execution plan that may be tactically
    adjusted by KPI pressure and post-result learning.

    Output path:
      data/output/{brand_id}/{page_id}/{campaign_id}/organic_posts/organic_strategy_output.json

    Hard rules:
    - IDs always come from Page_Channel_Library.
    - Page_Channel_Library.notes is the event switch only when it starts with `event:`:
        empty or non-event note => evergreen_growth
        `event: ...` => event_active or event_transition
    - Alysha master strategy is the source of truth for protected strategy fields.
    - Learning may change execution tactics only, never protected strategy fields.
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

    PROTECTED_ALYSHA_FIELDS = [
        "campaign_direction_alignment",
        "target_persona",
        "customer_psychology",
        "core_message",
        "offer_strategy",
        "reason_to_believe",
        "mechanism",
        "do_not_do",
    ]

    ALLOWED_ORGANIC_EXECUTION_FIELDS = [
        "audience_slice_execution",
        "scenario_execution",
        "hook_execution",
        "format_execution",
        "tone_execution",
        "content_archetype_execution",
        "posting_angle_execution",
        "seo_wording_execution",
        "reaction_trigger_execution",
        "social_engagement_tactics",
        "daily_learning_adjustments",
        "kpi_pressure_actions",
        "event_execution_policy",
    ]

    def __init__(
        self,
        strategy_prompt_file: str = "data/prompts/organic/organic_strategy_review_prompt.txt",
        alysha_strategy_file: str = "data/output/strategy_output.json",
        output_root: str = "data/output",
    ):
        self.strategy_prompt_file = strategy_prompt_file
        self.alysha_strategy_file = Path(alysha_strategy_file)
        self.output_root = Path(output_root)
        self.prompt_loader = PromptLoader()
        self.claude = ClaudeAPIAdapter()
        self.learning_memory = OrganicLearningMemoryStore()
        self.notifier = TelegramNotifier()
        self.organic_alysha_source_service = OrganicAlyshaSourceService(
            reference_strategy_file=str(self.alysha_strategy_file),
            output_root=str(self.output_root),
        )

    # -------------------------
    # Basic utilities
    # -------------------------
    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _iso_now(self) -> str:
        return self._now_utc().isoformat()

    def _clean_str(self, value: Any) -> str:
        return str(value or "").strip()

    def _event_note_from_notes(self, notes: Any) -> str:
        raw = self._clean_str(notes)
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered.startswith("event:"):
            return raw.split(":", 1)[1].strip()
        return ""

    def _safe_component(self, value: Any) -> str:
        raw = self._clean_str(value)
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
        return cleaned or "unknown"

    def _required_identifier(self, page_context: Dict[str, Any], key: str) -> str:
        value = self._clean_str(page_context.get(key))
        if not value:
            raise ValueError(f"Page_Channel_Library is missing required identifier: {key}")
        return value

    def _base_output_dir(self, page_context: Dict[str, Any]) -> Path:
        brand_id = self._required_identifier(page_context, "brand_id")
        page_id = self._required_identifier(page_context, "page_id")
        campaign_id = self._required_identifier(page_context, "campaign_id")
        return (
            self.output_root
            / self._safe_component(brand_id)
            / self._safe_component(page_id)
            / self._safe_component(campaign_id)
            / "organic_posts"
        )

    def strategy_output_path(self, page_context: Dict[str, Any]) -> Path:
        return self._base_output_dir(page_context) / "organic_strategy_output.json"

    def organic_output_path(self, page_context: Dict[str, Any]) -> Path:
        return self._base_output_dir(page_context) / "organic_output.json"

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

    def _deep_equal(self, left: Any, right: Any) -> bool:
        return self._stable_hash(left) == self._stable_hash(right)

    # -------------------------
    # Alysha Strategy handling
    # -------------------------
    def _load_alysha_strategy_output(self) -> Dict[str, Any]:
        payload = self._load_json(self.alysha_strategy_file, default={}) or {}
        if not payload:
            raise FileNotFoundError(
                f"Alysha strategy output not found or empty: {self.alysha_strategy_file}"
            )
        return payload

    def _strategy_data(self, strategy_output: Dict[str, Any]) -> Dict[str, Any]:
        data = strategy_output.get("data")
        if isinstance(data, dict):
            return data
        return strategy_output

    def _select_structured_alysha_source(self, strategy_output: Dict[str, Any]) -> Dict[str, Any]:
        data = self._strategy_data(strategy_output)
        structured = {}
        for key in self.ALYSHA_REQUIRED_SECTIONS:
            structured[key] = copy.deepcopy(data.get(key, [] if key != "do_not_do" else []))
        # Preserve campaign_direction_used / strategy_summary if present, but never raw response blobs.
        if data.get("campaign_direction_used") is not None:
            structured["campaign_direction_used"] = copy.deepcopy(data.get("campaign_direction_used"))
        if data.get("strategy_summary") is not None:
            structured["strategy_summary"] = copy.deepcopy(data.get("strategy_summary"))
        return structured

    def _alysha_mapping_audit(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        present = []
        missing = []
        for key in self.ALYSHA_REQUIRED_SECTIONS:
            value = structured.get(key)
            if value is None or value == [] or value == {} or value == "":
                missing.append(key)
            else:
                present.append(key)
        return {
            "mapping_target": "100% Alysha Strategy Engine compliance",
            "required_sections": list(self.ALYSHA_REQUIRED_SECTIONS),
            "present_sections": present,
            "missing_sections": missing,
            "compliance_status": "pass" if not missing else "warning_missing_alysha_sections",
        }

    def _protected_snapshot(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        return {key: copy.deepcopy(structured.get(key)) for key in self.PROTECTED_ALYSHA_FIELDS}

    def _protected_drift_detected(
        self,
        previous_strategy: Optional[Dict[str, Any]],
        current_snapshot: Dict[str, Any],
    ) -> bool:
        if not previous_strategy:
            return False
        previous_snapshot = (
            previous_strategy.get("alysha_compliance", {})
            .get("protected_alysha_snapshot")
        )
        if not previous_snapshot:
            return False
        return not self._deep_equal(previous_snapshot, current_snapshot)

    # -------------------------
    # Review policy
    # -------------------------
    def _parse_iso_dt(self, value: Any) -> Optional[datetime]:
        raw = self._clean_str(value)
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _days_since(self, value: Any) -> Optional[int]:
        dt = self._parse_iso_dt(value)
        if not dt:
            return None
        return max(0, (self._now_utc().date() - dt.date()).days)

    def _review_policy(
        self,
        existing_strategy: Optional[Dict[str, Any]],
        recent_learning: List[Dict[str, Any]],
        protected_alysha_drift: bool,
    ) -> Dict[str, Any]:
        min_days = int(os.getenv("ORGANIC_STRATEGY_MIN_DAYS_FOR_MAJOR_REVISION", "3"))
        min_learning_records = int(
            os.getenv("ORGANIC_STRATEGY_MIN_LEARNING_RECORDS_FOR_MAJOR_REVISION", "6")
        )
        force_revision = os.getenv(
            "ORGANIC_STRATEGY_FORCE_STABLE_REVISION", "false"
        ).lower() == "true"

        if not existing_strategy:
            return {
                "allow_stable_revision": True,
                "revision_reason": "No existing organic execution strategy; create a new Alysha-compliant translation.",
                "minimum_days_for_major_revision": min_days,
                "minimum_learning_records_for_major_revision": min_learning_records,
                "recent_learning_count": len(recent_learning),
                "days_since_last_stable_revision": None,
                "protected_alysha_drift": protected_alysha_drift,
            }

        last_major = (
            existing_strategy.get("last_stable_execution_revision_at")
            or existing_strategy.get("created_at")
        )
        days_since_major = self._days_since(last_major)
        enough_days = days_since_major is not None and days_since_major >= min_days
        enough_learning = len(recent_learning) >= min_learning_records
        allow = bool(force_revision or protected_alysha_drift or (enough_days and enough_learning))

        if protected_alysha_drift:
            reason = "Alysha source strategy changed; organic execution translation must be refreshed."
        elif force_revision:
            reason = "Stable organic execution revision was forced by environment configuration."
        elif allow:
            reason = "Minimum evidence window was met for a possible organic execution revision."
        else:
            reason = "Stable organic execution revision is guarded; use daily tactical adjustments only."

        return {
            "allow_stable_revision": allow,
            "revision_reason": reason,
            "minimum_days_for_major_revision": min_days,
            "minimum_learning_records_for_major_revision": min_learning_records,
            "recent_learning_count": len(recent_learning),
            "days_since_last_stable_revision": days_since_major,
            "protected_alysha_drift": protected_alysha_drift,
        }

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
            raise ValueError("Organic strategy review response did not contain valid JSON.")
        return json.loads(match.group())

    def _call_claude(self, prompt: str):
        try:
            return self.claude.run(prompt=prompt, max_tokens=8000, temperature=0.2)
        except TypeError:
            return self.claude.run(prompt=prompt)

    def _strategy_input(
        self,
        page_context: Dict[str, Any],
        campaign_kpi_context: Dict[str, Any],
        existing_strategy: Optional[Dict[str, Any]],
        recent_learning: List[Dict[str, Any]],
        review_policy: Dict[str, Any],
        structured_alysha_source: Dict[str, Any],
        mapping_audit: Dict[str, Any],
        protected_snapshot: Dict[str, Any],
        alysha_source_output_file: str,
        alysha_source_resolution: Dict[str, Any],
    ) -> Dict[str, Any]:
        notes = self._clean_str(page_context.get("notes"))
        event_note = self._event_note_from_notes(notes)
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
            "event_switch": {
                "notes_value": notes,
                "event_note": event_note,
                "has_event_note": bool(event_note),
                "event_detection_rule": "Only notes starting with 'event:' activate event-aware organic strategy.",
                "empty_or_non_event_notes_default_mode": "evergreen_growth",
                "event_notes_allowed_modes": ["event_active", "event_transition"],
            },
            "alysha_strategy_source_of_truth": structured_alysha_source,
            "alysha_mapping_audit": mapping_audit,
            "protected_alysha_snapshot": protected_snapshot,
            "campaign_kpi_context": campaign_kpi_context,
            "existing_organic_strategy": existing_strategy or {},
            "recent_organic_learning_context": recent_learning,
            "review_policy": review_policy,
            "allowed_organic_execution_fields": list(self.ALLOWED_ORGANIC_EXECUTION_FIELDS),
        }

    # -------------------------
    # Fallback response
    # -------------------------
    def _fallback_response(
        self,
        page_context: Dict[str, Any],
        campaign_kpi_context: Dict[str, Any],
        existing_strategy: Optional[Dict[str, Any]],
        recent_learning: List[Dict[str, Any]],
        structured_alysha_source: Dict[str, Any],
    ) -> Dict[str, Any]:
        notes = self._clean_str(page_context.get("notes"))
        event_note = self._event_note_from_notes(notes)
        strategy_mode = "evergreen_growth" if not event_note else "event_active"
        if existing_strategy:
            return {
                "strategy_mode": existing_strategy.get("strategy_mode") or strategy_mode,
                "event_context": existing_strategy.get("event_context") or {
                    "event_note": event_note,
                    "event_policy": "Only notes starting with 'event:' activate event-aware organic execution; fallback retained prior event interpretation when applicable.",
                    "event_relevance_today": "unclear",
                },
                "audience_psychology_layer": existing_strategy.get("audience_psychology_layer") or {
                    "source": "alysha_fallback",
                    "summary": "Retain Alysha customer psychology without autonomous changes.",
                    "belief_system": [],
                    "audience_rejection": [],
                    "identity_reinforcement": [],
                    "psychological_mechanism": [],
                    "tribal_validation": [],
                    "enemy_content": [],
                    "contrarian_content": [],
                    "deeper_archetypes": [],
                },
                "social_engagement_layer": existing_strategy.get("social_engagement_layer") or {
                    "facebook_native_engagement": [],
                    "identity_validation": [],
                    "comment_triggers": [],
                    "share_triggers": [],
                    "light_debate": [],
                    "rage_bait_light_guardrailed": [],
                    "engagement_guardrails": [],
                },
                "kpi_pressure_layer": {
                    "kpi_status": campaign_kpi_context.get("kpi_status"),
                    "content_intensity": campaign_kpi_context.get("content_intensity"),
                    "recommended_daily_post_count": campaign_kpi_context.get("recommended_daily_post_count"),
                    "instruction": campaign_kpi_context.get("generation_instruction"),
                },
                "organic_execution_strategy": existing_strategy.get("organic_execution_strategy") or {
                    "audience_slice_execution": [],
                    "scenario_execution": [],
                    "hook_execution": [],
                    "format_execution": [],
                    "tone_execution": [],
                    "content_archetype_execution": [],
                    "posting_angle_execution": [],
                    "seo_wording_execution": [],
                    "reaction_trigger_execution": [],
                    "event_execution_policy": [],
                    "kpi_pressure_actions": [],
                },
                "daily_learning_adjustments": {
                    "learning_evidence_summary": f"Fallback retained the current organic execution strategy. Recent learning records available: {len(recent_learning)}.",
                    "strengthen_today": [],
                    "reduce_today": [],
                    "next_batch_notes": [],
                },
                "review_decision": {
                    "update_type": "no_change",
                    "changed_fields": [],
                    "what_changed_vi": [],
                    "reason_vi": "Claude review chưa khả dụng, hệ thống giữ nguyên organic execution strategy hiện tại.",
                    "should_notify": False,
                },
            }

        primary_goal = "Support page growth while staying inside Alysha strategy truth."
        return {
            "strategy_mode": strategy_mode,
            "event_context": {
                "event_note": event_note,
                "event_policy": "notes trống hoặc không bắt đầu bằng 'event:' => evergreen; notes dạng 'event: ...' => event-aware execution.",
                "event_relevance_today": "unclear" if event_note else "not_applicable",
            },
            "audience_psychology_layer": {
                "source": "alysha_fallback",
                "summary": "Use Alysha target persona and customer psychology exactly as the strategy source of truth.",
                "belief_system": [],
                "audience_rejection": [],
                "identity_reinforcement": [],
                "psychological_mechanism": [],
                "tribal_validation": [],
                "enemy_content": [],
                "contrarian_content": [],
                "deeper_archetypes": [],
            },
            "social_engagement_layer": {
                "facebook_native_engagement": [],
                "identity_validation": [],
                "comment_triggers": [],
                "share_triggers": [],
                "light_debate": [],
                "rage_bait_light_guardrailed": [],
                "engagement_guardrails": [],
            },
            "kpi_pressure_layer": {
                "kpi_status": campaign_kpi_context.get("kpi_status"),
                "content_intensity": campaign_kpi_context.get("content_intensity"),
                "recommended_daily_post_count": campaign_kpi_context.get("recommended_daily_post_count"),
                "instruction": campaign_kpi_context.get("generation_instruction"),
            },
            "organic_execution_strategy": {
                "primary_goal": primary_goal,
                "audience_slice_execution": [],
                "scenario_execution": [],
                "hook_execution": [],
                "format_execution": [],
                "tone_execution": [],
                "content_archetype_execution": [],
                "posting_angle_execution": [],
                "seo_wording_execution": [],
                "reaction_trigger_execution": [],
                "event_execution_policy": [],
                "kpi_pressure_actions": [],
            },
            "daily_learning_adjustments": {
                "learning_evidence_summary": f"No AI review response; created a conservative Alysha-compliant organic execution shell. Recent learning records available: {len(recent_learning)}.",
                "strengthen_today": [],
                "reduce_today": [],
                "next_batch_notes": [],
            },
            "review_decision": {
                "update_type": "created",
                "changed_fields": [
                    "audience_psychology_layer",
                    "social_engagement_layer",
                    "kpi_pressure_layer",
                    "organic_execution_strategy",
                ],
                "what_changed_vi": [
                    "Tạo mới organic execution strategy bám Alysha để có thể sinh bài ngay hôm nay."
                ],
                "reason_vi": "Chưa có organic strategy trước đó; hệ thống tạo bản dịch thực thi organic từ Alysha strategy.",
                "should_notify": True,
            },
        }

    # -------------------------
    # Validation / merge
    # -------------------------
    def _assert_response_guardrails(self, response: Dict[str, Any]) -> None:
        mode = response.get("strategy_mode")
        if mode not in {"evergreen_growth", "event_active", "event_transition"}:
            raise ValueError(f"Invalid organic strategy mode: {mode}")
        for required_key in [
            "event_context",
            "audience_psychology_layer",
            "social_engagement_layer",
            "kpi_pressure_layer",
            "organic_execution_strategy",
            "daily_learning_adjustments",
            "review_decision",
        ]:
            if required_key not in response:
                raise ValueError(f"Organic strategy review response is missing: {required_key}")
        changed_fields = response.get("review_decision", {}).get("changed_fields") or []
        protected_set = set(self.PROTECTED_ALYSHA_FIELDS)
        if any(field in protected_set for field in changed_fields):
            raise ValueError(
                "Organic strategy review attempted to change protected Alysha fields. "
                f"changed_fields={changed_fields}"
            )

    def _preserve_stable_execution_if_guarded(
        self,
        response: Dict[str, Any],
        existing_strategy: Optional[Dict[str, Any]],
        review_policy: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not existing_strategy:
            return response
        allow_stable_revision = bool(review_policy.get("allow_stable_revision"))
        previous_mode = existing_strategy.get("strategy_mode")
        new_mode = response.get("strategy_mode")
        mode_changed = previous_mode != new_mode
        if allow_stable_revision or mode_changed:
            return response
        previous_execution = existing_strategy.get("organic_execution_strategy")
        if previous_execution:
            response["organic_execution_strategy"] = copy.deepcopy(previous_execution)
            decision = response.setdefault("review_decision", {})
            update_type = decision.get("update_type")
            if update_type == "stable_revision":
                decision["update_type"] = "daily_adjustment"
            decision.setdefault("changed_fields", [])
            decision["changed_fields"] = [
                field for field in decision["changed_fields"] if field != "organic_execution_strategy"
            ]
        return response

    def _build_final_strategy_output(
        self,
        page_context: Dict[str, Any],
        campaign_kpi_context: Dict[str, Any],
        response: Dict[str, Any],
        existing_strategy: Optional[Dict[str, Any]],
        recent_learning: List[Dict[str, Any]],
        review_policy: Dict[str, Any],
        structured_alysha_source: Dict[str, Any],
        mapping_audit: Dict[str, Any],
        protected_snapshot: Dict[str, Any],
        alysha_source_output_file: str,
        alysha_source_resolution: Dict[str, Any],
    ) -> Dict[str, Any]:
        now_iso = self._iso_now()
        response = self._preserve_stable_execution_if_guarded(
            response=response,
            existing_strategy=existing_strategy,
            review_policy=review_policy,
        )
        decision = response.get("review_decision") or {}
        update_type = decision.get("update_type") or "no_change"

        strategy_output = {
            "stage": "organic_strategy",
            "status": "ready",
            "created_at": (existing_strategy or {}).get("created_at") or now_iso,
            "last_reviewed_at": now_iso,
            "last_updated_at": now_iso if update_type != "no_change" else (existing_strategy or {}).get("last_updated_at") or now_iso,
            "last_stable_execution_revision_at": (
                now_iso
                if update_type in {"created", "stable_revision"}
                else (existing_strategy or {}).get("last_stable_execution_revision_at")
            ),
            "identifiers": {
                "brand_id": self._required_identifier(page_context, "brand_id"),
                "niche_id": self._required_identifier(page_context, "niche_id"),
                "page_id": self._required_identifier(page_context, "page_id"),
                "campaign_id": self._required_identifier(page_context, "campaign_id"),
                "platform_id": self._required_identifier(page_context, "platform_id"),
            },
            "strategy_mode": response.get("strategy_mode"),
            "event_context": response.get("event_context") or {},
            "alysha_compliance": {
                "source_of_truth": alysha_source_output_file,
                "upstream_organic_alysha_source": alysha_source_resolution,
                "mapping_target": "100% Alysha Strategy Engine compliance",
                "strategy_source_hash": self._stable_hash(structured_alysha_source),
                "mapping_audit": mapping_audit,
                "protected_alysha_fields": list(self.PROTECTED_ALYSHA_FIELDS),
                "protected_alysha_snapshot": protected_snapshot,
                "protected_fields_can_be_changed_by_organic_review": False,
                "allowed_organic_execution_fields": list(self.ALLOWED_ORGANIC_EXECUTION_FIELDS),
            },
            "alysha_strategy_source": structured_alysha_source,
            "audience_psychology_layer": response.get("audience_psychology_layer") or {},
            "social_engagement_layer": response.get("social_engagement_layer") or {},
            "kpi_pressure_layer": response.get("kpi_pressure_layer") or {},
            "organic_execution_strategy": response.get("organic_execution_strategy") or {},
            "daily_learning_adjustments": response.get("daily_learning_adjustments") or {},
            "recent_learning_summary": {
                "records_considered": len(recent_learning),
                "memory_source": "data/knowledge/organic_learning/{brand_id}/{brand_id}_{page_id}.jsonl",
            },
            "review_policy": review_policy,
            "review_decision": decision,
            "strategy_update_history": copy.deepcopy((existing_strategy or {}).get("strategy_update_history") or []),
            "campaign_kpi_context_snapshot": campaign_kpi_context,
        }

        if update_type != "no_change":
            strategy_output["strategy_update_history"].append(
                {
                    "reviewed_at": now_iso,
                    "update_type": update_type,
                    "changed_fields": decision.get("changed_fields") or [],
                    "what_changed_vi": decision.get("what_changed_vi") or [],
                    "reason_vi": decision.get("reason_vi") or "",
                }
            )
        return strategy_output

    # -------------------------
    # Telegram notifications
    # -------------------------
    def _notify_if_changed(self, strategy_output: Dict[str, Any]) -> None:
        decision = strategy_output.get("review_decision") or {}
        if not decision.get("should_notify"):
            return
        identifiers = strategy_output.get("identifiers") or {}
        changed_vi = decision.get("what_changed_vi") or []
        changed_lines = "\n".join([f"- {item}" for item in changed_vi]) if changed_vi else "- Không có mô tả thay đổi chi tiết."
        message = (
            "🧠 Organic Strategy Review Updated\n"
            f"Brand: {identifiers.get('brand_id', '')}\n"
            f"Page: {identifiers.get('page_id', '')}\n"
            f"Campaign: {identifiers.get('campaign_id', '')}\n"
            f"Mode: {strategy_output.get('strategy_mode', '')}\n"
            f"Update type: {decision.get('update_type', '')}\n\n"
            "Thay đổi:\n"
            f"{changed_lines}\n\n"
            f"Lý do: {decision.get('reason_vi', '')}"
        )
        self.notifier.send(message)

    # -------------------------
    # Public API
    # -------------------------
    def review_or_create(
        self,
        page_context: Dict[str, Any],
        campaign_kpi_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        strategy_path = self.strategy_output_path(page_context)
        organic_output_path = self.organic_output_path(page_context)
        existing_strategy = self._load_json(strategy_path, default=None)

        alysha_source_resolution = self.organic_alysha_source_service.resolve(
            page_context=page_context,
            campaign_kpi_context=campaign_kpi_context,
        )
        alysha_strategy_output = alysha_source_resolution["source_output"]
        structured_alysha_source = self._select_structured_alysha_source(alysha_strategy_output)
        mapping_audit = self._alysha_mapping_audit(structured_alysha_source)
        protected_snapshot = self._protected_snapshot(structured_alysha_source)
        protected_drift = self._protected_drift_detected(existing_strategy, protected_snapshot)

        learning_limit = int(os.getenv("ORGANIC_LEARNING_CONTEXT_LIMIT", "20"))
        recent_learning = self.learning_memory.load_recent(
            brand_id=self._required_identifier(page_context, "brand_id"),
            page_id=self._required_identifier(page_context, "page_id"),
            limit=learning_limit,
        )
        review_policy = self._review_policy(
            existing_strategy=existing_strategy,
            recent_learning=recent_learning,
            protected_alysha_drift=protected_drift,
        )

        strategy_input = self._strategy_input(
            page_context=page_context,
            campaign_kpi_context=campaign_kpi_context,
            existing_strategy=existing_strategy,
            recent_learning=recent_learning,
            review_policy=review_policy,
            structured_alysha_source=structured_alysha_source,
            mapping_audit=mapping_audit,
            protected_snapshot=protected_snapshot,
            alysha_source_output_file=alysha_source_resolution.get("source_output_file", ""),
            alysha_source_resolution={
                "source_output_file": alysha_source_resolution.get("source_output_file", ""),
                "source_refreshed": alysha_source_resolution.get("source_refreshed", False),
                "source_refresh_reason": alysha_source_resolution.get("source_refresh_reason", ""),
            },
        )

        readiness = self.claude.readiness()
        if readiness.get("ready"):
            prompt = self.prompt_loader.render(
                self.strategy_prompt_file,
                {"ORGANIC_STRATEGY_INPUT": json.dumps(strategy_input, ensure_ascii=False, indent=2)},
            )
            response = self._parse_json_response(self._call_claude(prompt))
        else:
            response = self._fallback_response(
                page_context=page_context,
                campaign_kpi_context=campaign_kpi_context,
                existing_strategy=existing_strategy,
                recent_learning=recent_learning,
                structured_alysha_source=structured_alysha_source,
            )

        self._assert_response_guardrails(response)
        final_strategy = self._build_final_strategy_output(
            page_context=page_context,
            campaign_kpi_context=campaign_kpi_context,
            response=response,
            existing_strategy=existing_strategy,
            recent_learning=recent_learning,
            review_policy=review_policy,
            structured_alysha_source=structured_alysha_source,
            mapping_audit=mapping_audit,
            protected_snapshot=protected_snapshot,
            alysha_source_output_file=alysha_source_resolution.get("source_output_file", ""),
            alysha_source_resolution={
                "source_output_file": alysha_source_resolution.get("source_output_file", ""),
                "source_refreshed": alysha_source_resolution.get("source_refreshed", False),
                "source_refresh_reason": alysha_source_resolution.get("source_refresh_reason", ""),
            },
        )
        self._write_json(strategy_path, final_strategy)
        self._notify_if_changed(final_strategy)
        return {
            "strategy_output": final_strategy,
            "strategy_output_file": str(strategy_path),
            "organic_output_file": str(organic_output_path),
            "review_decision": final_strategy.get("review_decision") or {},
            "recent_organic_learning_context": recent_learning,
            "alysha_source_output_file": alysha_source_resolution.get("source_output_file", ""),
            "alysha_source_refreshed": alysha_source_resolution.get("source_refreshed", False),
            "alysha_source_refresh_reason": alysha_source_resolution.get("source_refresh_reason", ""),
        }
