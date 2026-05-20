from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_OUTPUT_GROUPS = ("flat_mockup", "worn_mockup", "lifestyle_scene")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str | Path) -> Path:
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def read_json(path: str | Path, *, required: bool = True) -> dict[str, Any] | list[Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        if required:
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        return None
    return json.loads(file_path.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return file_path


def compact_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def safe_name(value: str) -> str:
    cleaned = []
    for char in str(value).strip():
        cleaned.append(char if char.isalnum() or char in ("_", "-", ".") else "_")
    result = "".join(cleaned).strip("_")
    return result or "unknown"


@dataclass(frozen=True)
class PodCampaignPaths:
    brand_id: str
    campaign_id: str
    data_root: Path = Path("data")

    @property
    def campaign_root(self) -> Path:
        return self.data_root / "brands" / safe_name(self.brand_id) / "pod" / "campaigns" / safe_name(self.campaign_id)

    @property
    def step_1_strategy_dir(self) -> Path:
        return self.campaign_root / "01_pod_strategy"

    @property
    def step_2_brief_dir(self) -> Path:
        return self.campaign_root / "02_pod_design_brief"

    @property
    def step_3_brief_eval_dir(self) -> Path:
        return self.campaign_root / "03_pod_brief_eval"

    @property
    def step_4_translation_dir(self) -> Path:
        return self.campaign_root / "04_open_design_translation"

    @property
    def step_5_render_dir(self) -> Path:
        return self.campaign_root / "05_comfyui_render_worker"

    @property
    def step_6_visual_eval_dir(self) -> Path:
        return self.campaign_root / "06_visual_output_eval"

    @property
    def step_7_human_review_dir(self) -> Path:
        return self.campaign_root / "07_human_review"

    @property
    def step_8_learning_dir(self) -> Path:
        return self.campaign_root / "08_learning"

    @property
    def reports_dir(self) -> Path:
        return self.campaign_root / "reports"

    @property
    def usage_dir(self) -> Path:
        return self.campaign_root / "usage"

    def ensure(self) -> "PodCampaignPaths":
        for path in (
            self.campaign_root,
            self.step_1_strategy_dir,
            self.step_2_brief_dir,
            self.step_3_brief_eval_dir,
            self.step_4_translation_dir,
            self.step_5_render_dir,
            self.step_6_visual_eval_dir,
            self.step_7_human_review_dir,
            self.step_8_learning_dir,
            self.reports_dir,
            self.usage_dir,
        ):
            ensure_dir(path)
        return self


@dataclass
class UsageEvent:
    step: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    status: str = "available"
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageLedger:
    pricebook: dict[str, dict[str, float]]
    events: list[UsageEvent] = field(default_factory=list)

    def record(
        self,
        *,
        step: str,
        provider: str,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        tokens_available = input_tokens is not None and output_tokens is not None
        input_value = int(input_tokens or 0)
        output_value = int(output_tokens or 0)
        pricing = self.pricebook.get(model) or self.pricebook.get("default") or {}
        input_rate = float(pricing.get("input_usd_per_million_tokens", 0.0))
        output_rate = float(pricing.get("output_usd_per_million_tokens", 0.0))
        input_cost = (input_value / 1_000_000) * input_rate
        output_cost = (output_value / 1_000_000) * output_rate
        event = UsageEvent(
            step=step,
            provider=provider,
            model=model,
            input_tokens=input_value,
            output_tokens=output_value,
            input_cost_usd=round(input_cost, 8),
            output_cost_usd=round(output_cost, 8),
            total_cost_usd=round(input_cost + output_cost, 8),
            status="available" if tokens_available else "unavailable_from_api_response",
            metadata=metadata or {},
        )
        self.events.append(event)
        return event

    def summary(self) -> dict[str, Any]:
        by_step: dict[str, dict[str, Any]] = {}
        total_input = 0
        total_output = 0
        total_cost = 0.0
        unavailable_events = 0
        for event in self.events:
            total_input += event.input_tokens
            total_output += event.output_tokens
            total_cost += event.total_cost_usd
            if event.status != "available":
                unavailable_events += 1
            bucket = by_step.setdefault(
                event.step,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_cost_usd": 0.0,
                    "models": [],
                    "usage_unavailable_calls": 0,
                },
            )
            bucket["calls"] += 1
            bucket["input_tokens"] += event.input_tokens
            bucket["output_tokens"] += event.output_tokens
            bucket["total_cost_usd"] = round(bucket["total_cost_usd"] + event.total_cost_usd, 8)
            if event.model not in bucket["models"]:
                bucket["models"].append(event.model)
            if event.status != "available":
                bucket["usage_unavailable_calls"] += 1
        return {
            "total_calls": len(self.events),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost_usd": round(total_cost, 8),
            "usage_unavailable_calls": unavailable_events,
            "by_step": by_step,
            "events": [asdict(event) for event in self.events],
        }


class SafeTelegramNotifier:
    """
    Uses project TelegramNotifier if available.
    Fallback: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID.
    Notification failures never stop production jobs.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.delegate = None
        if not enabled:
            return
        try:
            from core.notifications.telegram_notifier import TelegramNotifier  # type: ignore
            self.delegate = TelegramNotifier()
        except Exception:
            self.delegate = None

    def send(self, text: str) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled"}
        try:
            if self.delegate is not None:
                if hasattr(self.delegate, "send_message"):
                    self.delegate.send_message(text)
                elif hasattr(self.delegate, "send"):
                    self.delegate.send(text)
                else:
                    raise AttributeError("TelegramNotifier has no supported send method.")
                return {"status": "sent", "mode": "project_delegate"}

            import requests

            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
            if not bot_token or not chat_id:
                return {"status": "skipped_missing_env"}
            response = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=30,
            )
            response.raise_for_status()
            return {"status": "sent", "mode": "fallback_http"}
        except Exception as exc:
            return {"status": "failed_but_ignored", "error": str(exc)}


def load_settings(config_file: str | Path | None) -> dict[str, Any]:
    if not config_file:
        return {}
    loaded = read_json(config_file, required=False)
    return loaded if isinstance(loaded, dict) else {}


def usage_summary_for_step(ledger: UsageLedger, step: str) -> dict[str, Any]:
    return ledger.summary().get("by_step", {}).get(
        step,
        {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
            "models": [],
            "usage_unavailable_calls": 0,
        },
    )
