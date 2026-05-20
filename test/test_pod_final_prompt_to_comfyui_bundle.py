from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config.paths import GLOBAL_CONFIG_DIR
from core.notifications.telegram_notifier import TelegramNotifier
from core.services.pod_cache_service import PodLLMOutputCache, stable_hash
from core.services.pod_input_resolver import PodInputResolver
from core.services.pod_pipeline_utils import safe_name, write_json, read_json

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = "claude-sonnet-4-6"


def extract_text(response_payload: dict[str, Any]) -> str:
    return "\n".join(
        block.get("text", "")
        for block in response_payload.get("content", []) or []
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(1))
    if not isinstance(parsed, dict):
        raise TypeError("Expected JSON object from Claude.")
    return parsed


def estimate_cost_usd(usage: dict[str, Any], *, cache_hit: bool = False) -> dict[str, Any]:
    if cache_hit:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "cache_hit": True,
        }
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "total_cost_usd": round(input_tokens / 1_000_000 * 3.0 + output_tokens / 1_000_000 * 15.0, 8),
        "cache_hit": False,
    }


def generate_bundle(
    *,
    brand_id: str,
    campaign_id: str,
    final_prompt: str,
    sample_image_url: str,
    product_entry: dict[str, Any],
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required.")

    system = (
        "You are Step [4] Open Design / Generative Media Translation Layer. "
        "Convert an approved apparel final prompt into ChatGPT image prompts and ComfyUI render requests. "
        "Return JSON only."
    )
    user_payload = {
        "task": "Create a ComfyUI-ready render request bundle for a two-sided POD product.",
        "brand_id": brand_id,
        "campaign_id": campaign_id,
        "sample_image_url": sample_image_url,
        "product_catalog_entry": product_entry,
        "approved_final_design_prompt": final_prompt,
        "hard_requirements": [
            "Return separate front and back outputs. Products always have two sides.",
            "Return both chatgpt_image_prompt and comfyui generation payload for each side.",
            "Only create two render requests for now: front_flat_mockup and back_flat_mockup.",
            "Each positive_prompt must be concise enough for image generation but preserve layout, color, logo/text placement, pattern/motif placement, trims, and material notes.",
            "Each negative_prompt must block official NFL/team marks, trademark copying, unreadable text, wrong side, distorted apparel, bad mockup, low quality.",
            "Do not claim rendering has happened.",
            "Keep seed null so render worker can assign it later.",
        ],
        "return_schema": {
            "stage": "open_design_generative_media_translation",
            "translation_version": "test_v001",
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "source": {
                "source_column": "final prompt ( bao gồm phần giữ của mẫu gốc và thêm các điểm cải tiến",
                "final_prompt_hash": "",
                "sample_image_url": sample_image_url,
            },
            "chatgpt_image_prompts": [
                {
                    "request_id": "front_flat_mockup",
                    "view": "front",
                    "output_group": "flat_mockup",
                    "prompt": "",
                },
                {
                    "request_id": "back_flat_mockup",
                    "view": "back",
                    "output_group": "flat_mockup",
                    "prompt": "",
                },
            ],
            "comfyui_render_requests": [
                {
                    "request_id": "front_flat_mockup",
                    "brand_id": brand_id,
                    "campaign_id": campaign_id,
                    "job_id": "",
                    "view": "front",
                    "output_group": "flat_mockup",
                    "workflow_id_hint": "pod_apparel_flat_mockup_front",
                    "generation_payload": {
                        "positive_prompt": "",
                        "negative_prompt": "",
                        "reference_image_url": sample_image_url,
                        "seed": None,
                        "width": 1024,
                        "height": 1024,
                        "steps": 30,
                        "cfg": 7,
                        "sampler": "dpmpp_2m",
                        "scheduler": "karras",
                        "checkpoint": "",
                    },
                    "metadata": {
                        "product_ref_id": "",
                        "product_name_or_scope": "",
                        "attempt_no": 1,
                    },
                },
                {
                    "request_id": "back_flat_mockup",
                    "brand_id": brand_id,
                    "campaign_id": campaign_id,
                    "job_id": "",
                    "view": "back",
                    "output_group": "flat_mockup",
                    "workflow_id_hint": "pod_apparel_flat_mockup_back",
                    "generation_payload": {
                        "positive_prompt": "",
                        "negative_prompt": "",
                        "reference_image_url": sample_image_url,
                        "seed": None,
                        "width": 1024,
                        "height": 1024,
                        "steps": 30,
                        "cfg": 7,
                        "sampler": "dpmpp_2m",
                        "scheduler": "karras",
                        "checkpoint": "",
                    },
                    "metadata": {
                        "product_ref_id": "",
                        "product_name_or_scope": "",
                        "attempt_no": 1,
                    },
                },
            ],
            "translation_notes": {
                "workflow_assumptions": [],
                "items_for_render_worker_configuration": [],
                "items_for_future_iteration": [],
            },
        },
    }

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 8000,
            "temperature": 0.2,
            "system": system,
            "messages": [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
        },
        timeout=240,
    )
    response.raise_for_status()
    raw = response.json()
    parsed = parse_json_response(extract_text(raw))
    parsed.setdefault("source", {})["final_prompt_hash"] = stable_hash(final_prompt)
    return parsed, {
        "provider": "anthropic",
        "model": model,
        "response_id": raw.get("id"),
        "usage": raw.get("usage") or {},
    }


def notify_result(report: dict[str, Any]) -> dict[str, Any]:
    cost = report["cost_estimate"]
    message = (
        "POD Step [4] ComfyUI bundle test completed\n"
        f"Brand: {report['brand_id']}\n"
        f"Row: {report['row_number']}\n"
        f"Cache: {report['api_meta'].get('cache_status')}\n"
        f"Total tokens: {cost['total_tokens']}\n"
        f"Estimated cost: ${cost['total_cost_usd']:.6f}\n"
        f"Output: {report['outputs']['comfyui_render_request_bundle']}"
    )
    return TelegramNotifier().send(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test: convert final prompt to ChatGPT prompts + ComfyUI bundle.")
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--row-number", type=int, default=4)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--telegram-disabled", action="store_true")
    args = parser.parse_args()

    schema = read_json(GLOBAL_CONFIG_DIR / "gsheet_schema.json")["modules"]["pod_campaign"]
    fields = schema["campaign_intake"]["field_mappings"]
    source = PodInputResolver()._load_campaign_source(args.brand_id)
    ws = source["campaign_worksheet"]
    headers = [str(value).strip() for value in ws.row_values(3)]
    header_map = {header: index + 1 for index, header in enumerate(headers) if header}
    final_col = fields["final_prompt_from_sample"]
    sample_col = fields["sample_image_url"]

    row_values = ws.row_values(args.row_number)
    campaign_row = {
        header: row_values[index] if index < len(row_values) else ""
        for index, header in enumerate(headers)
        if header
    }
    final_prompt = campaign_row.get(final_col, "")
    if not final_prompt.strip():
        raise ValueError("final prompt column is empty.")
    product_entry = PodInputResolver()._find_product_entry(
        product_rows=source["product_rows"],
        schema=source["schema"],
        product_ref_id=campaign_row.get("product_ref_id"),
    )
    campaign_id = safe_name(campaign_row.get("campaign_id") or campaign_row.get("campaign_name") or f"row_{args.row_number}")

    cache_input = {
        "prompt_version": "final_prompt_to_comfyui_bundle_v001",
        "model": args.model,
        "brand_id": args.brand_id,
        "campaign_id": campaign_id,
        "final_prompt_hash": stable_hash(final_prompt),
        "sample_image_url": campaign_row.get(sample_col, ""),
        "product_entry_hash": stable_hash(product_entry),
        "output_requests": ["front_flat_mockup", "back_flat_mockup"],
    }
    cache = PodLLMOutputCache(brand_id=args.brand_id, namespace="final_prompt_to_comfyui_bundle")
    input_hash = cache.input_hash(cache_input)
    cached = cache.get(input_hash)
    if cached:
        bundle = cached["output"]
        meta = {**cached.get("api_meta", {}), "cache_status": "hit", "cache_file": cached["cache_file"], "input_hash": input_hash}
    else:
        bundle, meta = generate_bundle(
            brand_id=args.brand_id,
            campaign_id=campaign_id,
            final_prompt=final_prompt,
            sample_image_url=campaign_row.get(sample_col, ""),
            product_entry=product_entry,
            model=args.model,
        )
        cache_file = cache.set(input_hash=input_hash, output=bundle, api_meta=meta, cache_input=cache_input)
        meta = {**meta, "cache_status": "miss_stored", "cache_file": str(cache_file), "input_hash": input_hash}

    campaign_root = PROJECT_ROOT / "data" / "brands" / args.brand_id / "pod" / "campaigns" / campaign_id
    output_dir = campaign_root / "04_open_design_translation"
    bundle_file = write_json(output_dir / "comfyui_render_request_bundle.json", bundle)
    prompts_file = write_json(
        output_dir / "chatgpt_image_prompts.json",
        {
            "brand_id": args.brand_id,
            "campaign_id": campaign_id,
            "prompts": bundle.get("chatgpt_image_prompts", []),
        },
    )
    translation_file = write_json(output_dir / "pod_open_design_translation.json", bundle)
    meta_file = write_json(output_dir / "pod_open_design_translation_api_meta.json", meta)

    report = {
        "status": "success",
        "brand_id": args.brand_id,
        "campaign_id": campaign_id,
        "row_number": args.row_number,
        "source_column": final_col,
        "api_meta": meta,
        "cost_estimate": estimate_cost_usd(meta.get("usage") or {}, cache_hit=meta.get("cache_status") == "hit"),
        "outputs": {
            "pod_open_design_translation": str(translation_file),
            "chatgpt_image_prompts": str(prompts_file),
            "comfyui_render_request_bundle": str(bundle_file),
            "api_meta": str(meta_file),
        },
    }
    if not args.telegram_disabled:
        report["telegram_notification"] = notify_result(report)
    report_file = write_json(output_dir / "pod_final_prompt_to_comfyui_bundle_test_report.json", report)
    print(json.dumps({"status": "success", "report_file": str(report_file), "cache_status": meta.get("cache_status")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
