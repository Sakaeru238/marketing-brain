from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from core.services.pod_llm_client import PodClaudeJsonClient
from core.services.pod_pipeline_utils import (
    PodCampaignPaths,
    SafeTelegramNotifier,
    UsageLedger,
    load_settings,
    read_json,
    usage_summary_for_step,
    write_json,
)


DEFAULT_CONFIG_FILE = "config/pod/pod_strategy_brief_settings.json"


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--campaign-id", default=None)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--config-file", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--model", default=None)
    parser.add_argument("--telegram-disabled", action="store_true")


def build_runtime(args: argparse.Namespace) -> tuple[dict[str, Any], PodCampaignPaths, UsageLedger, PodClaudeJsonClient, SafeTelegramNotifier]:
    if not getattr(args, "campaign_id", None):
        raise ValueError("campaign_id is required before building POD runtime.")
    settings = load_settings(args.config_file)
    model = args.model or settings.get("llm", {}).get("model") or os.getenv("POD_STRATEGY_BRIEF_MODEL") or "claude-sonnet-4-6"
    pricebook = settings.get("pricing", {}).get("pricebook") or {
        "claude-sonnet-4-6": {
            "input_usd_per_million_tokens": 3.0,
            "output_usd_per_million_tokens": 15.0,
        },
        "default": {
            "input_usd_per_million_tokens": 0.0,
            "output_usd_per_million_tokens": 0.0,
        },
    }
    ledger = UsageLedger(pricebook=pricebook)
    client = PodClaudeJsonClient(
        model=model,
        usage_ledger=ledger,
        timeout_seconds=int(settings.get("llm", {}).get("timeout_seconds", 300)),
    )
    notifier = SafeTelegramNotifier(enabled=not args.telegram_disabled)
    paths = PodCampaignPaths(
        brand_id=args.brand_id,
        campaign_id=args.campaign_id,
        data_root=Path(args.data_root),
    ).ensure()
    return settings, paths, ledger, client, notifier


def notify_step_started(notifier: SafeTelegramNotifier, title: str, brand_id: str, campaign_id: str) -> None:
    notifier.send(f"🚀 {title} started\nBrand: {brand_id}\nCampaign: {campaign_id}")


def notify_step_completed(
    notifier: SafeTelegramNotifier,
    *,
    title: str,
    brand_id: str,
    campaign_id: str,
    ledger: UsageLedger,
    step_name: str,
    extra: str = "",
) -> None:
    usage = usage_summary_for_step(ledger, step_name)
    notifier.send(
        f"✅ {title} completed\n"
        f"Brand: {brand_id}\nCampaign: {campaign_id}\n"
        f"Calls: {usage.get('calls', 0)}\n"
        f"Tokens: {usage.get('input_tokens', 0) + usage.get('output_tokens', 0)} "
        f"(in {usage.get('input_tokens', 0)} / out {usage.get('output_tokens', 0)})\n"
        f"Cost: ${usage.get('total_cost_usd', 0.0):.6f}"
        + (f"\n{extra}" if extra else "")
    )


def notify_step_failed(notifier: SafeTelegramNotifier, title: str, brand_id: str, campaign_id: str, error: Exception) -> None:
    notifier.send(f"❌ {title} failed\nBrand: {brand_id}\nCampaign: {campaign_id}\nError: {error}")


def write_usage_and_report(
    *,
    ledger: UsageLedger,
    usage_file: str | Path,
    report_file: str | Path,
    report: dict[str, Any],
) -> None:
    summary = ledger.summary()
    write_json(usage_file, summary)
    report["usage_summary"] = summary
    write_json(report_file, report)
