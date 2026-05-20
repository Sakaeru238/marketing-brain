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
from core.services.pod_pipeline_utils import read_json, write_json

load_dotenv(PROJECT_ROOT / ".env")


DEFAULT_MODEL = "claude-sonnet-4-6"
PRICEBOOK = {
    "claude-sonnet-4-6": {
        "input_usd_per_million_tokens": 3.0,
        "output_usd_per_million_tokens": 15.0,
    },
    "default": {
        "input_usd_per_million_tokens": 0.0,
        "output_usd_per_million_tokens": 0.0,
    },
}


def load_schema() -> dict[str, Any]:
    payload = read_json(GLOBAL_CONFIG_DIR / "gsheet_schema.json")
    return payload["modules"]["pod_campaign"]


def extract_text(response_payload: dict[str, Any]) -> str:
    chunks = []
    for block in response_payload.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text":
            chunks.append(str(block.get("text", "")))
    return "\n".join(chunks).strip()


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


def estimate_cost_usd(model: str, usage: dict[str, Any]) -> dict[str, Any]:
    pricing = PRICEBOOK.get(model) or PRICEBOOK["default"]
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    input_cost = input_tokens / 1_000_000 * float(pricing["input_usd_per_million_tokens"])
    output_cost = output_tokens / 1_000_000 * float(pricing["output_usd_per_million_tokens"])
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": round(input_cost, 8),
        "output_cost_usd": round(output_cost, 8),
        "total_cost_usd": round(input_cost + output_cost, 8),
    }


def find_target_row(source: dict[str, Any], improvements_column: str, row_number: int | None) -> dict[str, Any]:
    for item in source["campaign_rows"]:
        if row_number and item["row_number"] != row_number:
            continue
        if str(item["data"].get(improvements_column) or "").strip():
            return item
    raise ValueError(f"No campaign row found with non-empty improvements column: {improvements_column}")


def generate_design_brief(
    *,
    brand_context: dict[str, Any],
    campaign_row: dict[str, Any],
    product_entry: dict[str, Any],
    sample_analysis: str,
    improvement_points: str,
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required.")

    system = (
        "You are adapting julianoczkowski/designer-skills for POD apparel design briefing. "
        "Create a precise production-ready design brief from the sample improvement points. "
        "Return JSON only."
    )
    user_payload = {
        "task": "Create a POD apparel design brief using the sample improvement points.",
        "brand_context": brand_context,
        "campaign_intake": campaign_row,
        "product_catalog_entry": product_entry,
        "sample_image_analysis": sample_analysis,
        "sample_improvement_points": improvement_points,
        "hard_requirements": [
            "Describe the front side of the shirt clearly.",
            "Describe the back side of the shirt clearly.",
            "Specify layout, color system, logo placement, main text placement, supporting text placement, pattern/motif placement, line work, trims, collar/sleeve details, and visual hierarchy.",
            "Separate front and back design instructions. Do not merge them into one vague description.",
            "Respect must_keep_elements and must_avoid_elements from campaign intake.",
            "Do not use official team logos, NFL marks, trademarked symbols, or direct copies.",
            "Make the brief practical for POD execution on the chosen SKU.",
        ],
        "return_schema": {
            "stage": "pod_design_brief_from_sample_improvements",
            "brief_version": "test_v001",
            "design_summary": "",
            "front_design": {
                "overall_layout": "",
                "color_system": "",
                "main_logo_or_crest_placement": "",
                "main_text_placement": "",
                "supporting_text_placement": "",
                "pattern_and_motif_placement": "",
                "line_work_and_decorative_details": "",
                "collar_sleeve_trim_details": "",
                "visual_hierarchy": "",
                "must_avoid_on_front": [],
            },
            "back_design": {
                "overall_layout": "",
                "color_system": "",
                "main_logo_or_crest_placement": "",
                "main_text_placement": "",
                "supporting_text_placement": "",
                "pattern_and_motif_placement": "",
                "line_work_and_decorative_details": "",
                "collar_sleeve_trim_details": "",
                "visual_hierarchy": "",
                "must_avoid_on_back": [],
            },
            "shared_design_system": {
                "style_direction": "",
                "palette": [],
                "typography": "",
                "symbol_language": "",
                "pattern_language": "",
                "material_and_print_notes": "",
            },
            "pod_execution_notes": {
                "print_or_embroidery_method": "",
                "placement_precision": [],
                "production_risks": [],
                "quality_checklist": [],
            },
            "brand_and_ip_safety": {
                "safe_substitutions": [],
                "forbidden_elements": [],
                "review_notes": [],
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
            "max_tokens": 6000,
            "temperature": 0.2,
            "system": system,
            "messages": [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
        },
        timeout=180,
    )
    response.raise_for_status()
    raw = response.json()
    parsed = parse_json_response(extract_text(raw))
    return parsed, {
        "provider": "anthropic",
        "model": model,
        "response_id": raw.get("id"),
        "usage": raw.get("usage") or {},
    }


def build_final_prompt(brief: dict[str, Any]) -> str:
    front = brief.get("front_design") or {}
    back = brief.get("back_design") or {}
    shared = brief.get("shared_design_system") or {}
    execution = brief.get("pod_execution_notes") or {}
    safety = brief.get("brand_and_ip_safety") or {}

    return "\n".join(
        [
            "FINAL DESIGN PROMPT — keep the useful structure of the sample shirt and apply the campaign improvements.",
            "",
            "DESIGN SUMMARY:",
            str(brief.get("design_summary") or ""),
            "",
            "FRONT SIDE:",
            f"- Overall layout: {front.get('overall_layout', '')}",
            f"- Color system: {front.get('color_system', '')}",
            f"- Logo / crest placement: {front.get('main_logo_or_crest_placement', '')}",
            f"- Main text placement: {front.get('main_text_placement', '')}",
            f"- Supporting text placement: {front.get('supporting_text_placement', '')}",
            f"- Pattern / motif placement: {front.get('pattern_and_motif_placement', '')}",
            f"- Line work / decorative details: {front.get('line_work_and_decorative_details', '')}",
            f"- Collar / sleeve / trim details: {front.get('collar_sleeve_trim_details', '')}",
            f"- Visual hierarchy: {front.get('visual_hierarchy', '')}",
            "",
            "BACK SIDE:",
            f"- Overall layout: {back.get('overall_layout', '')}",
            f"- Color system: {back.get('color_system', '')}",
            f"- Logo / crest placement: {back.get('main_logo_or_crest_placement', '')}",
            f"- Main text placement: {back.get('main_text_placement', '')}",
            f"- Supporting text placement: {back.get('supporting_text_placement', '')}",
            f"- Pattern / motif placement: {back.get('pattern_and_motif_placement', '')}",
            f"- Line work / decorative details: {back.get('line_work_and_decorative_details', '')}",
            f"- Collar / sleeve / trim details: {back.get('collar_sleeve_trim_details', '')}",
            f"- Visual hierarchy: {back.get('visual_hierarchy', '')}",
            "",
            "SHARED DESIGN SYSTEM:",
            f"- Style direction: {shared.get('style_direction', '')}",
            f"- Palette: {', '.join(map(str, shared.get('palette') or []))}",
            f"- Typography: {shared.get('typography', '')}",
            f"- Symbol language: {shared.get('symbol_language', '')}",
            f"- Pattern language: {shared.get('pattern_language', '')}",
            f"- Material / print notes: {shared.get('material_and_print_notes', '')}",
            "",
            "POD EXECUTION:",
            f"- Print / embroidery method: {execution.get('print_or_embroidery_method', '')}",
            f"- Placement precision: {', '.join(map(str, execution.get('placement_precision') or []))}",
            f"- Production risks: {', '.join(map(str, execution.get('production_risks') or []))}",
            f"- Quality checklist: {', '.join(map(str, execution.get('quality_checklist') or []))}",
            "",
            "BRAND AND IP SAFETY:",
            f"- Safe substitutions: {', '.join(map(str, safety.get('safe_substitutions') or []))}",
            f"- Forbidden elements: {', '.join(map(str, safety.get('forbidden_elements') or []))}",
            f"- Review notes: {', '.join(map(str, safety.get('review_notes') or []))}",
        ]
    ).strip()


def notify_result(report: dict[str, Any]) -> dict[str, Any]:
    cost = report["cost_estimate"]
    message = (
        "POD design brief from sample improvements completed\n"
        f"Brand: {report['brand_id']}\n"
        f"Row: {report['row_number']}\n"
        f"Model: {report['api_meta']['model']}\n"
        f"Input tokens: {cost['input_tokens']}\n"
        f"Output tokens: {cost['output_tokens']}\n"
        f"Total tokens: {cost['total_tokens']}\n"
        f"Estimated cost: ${cost['total_cost_usd']:.6f}"
    )
    return TelegramNotifier().send(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test: create POD design brief from sample improvement points.")
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--row-number", type=int, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-file", default="performance/test_results/pod_design_brief_from_improvements_test.json")
    parser.add_argument("--telegram-disabled", action="store_true")
    args = parser.parse_args()

    schema = load_schema()
    mappings = schema["campaign_intake"]["field_mappings"]
    analysis_column = mappings["sample_image_analysis"]
    improvements_column = mappings["sample_image_improvement_points"]
    final_prompt_column = mappings["final_prompt_from_sample"]

    resolver = PodInputResolver()
    source = resolver._load_campaign_source(args.brand_id)
    target = find_target_row(source, improvements_column, args.row_number)
    campaign_row = target["data"]
    product_entry = resolver._find_product_entry(
        product_rows=source["product_rows"],
        schema=source["schema"],
        product_ref_id=campaign_row.get("product_ref_id"),
    )
    brand_paths = resolver.context_resolver.resolve(args.brand_id)
    brand_context = read_json(brand_paths["brand_context_json_file"])

    sample_analysis = campaign_row.get(analysis_column, "")
    improvement_points = campaign_row[improvements_column]
    cache_input = {
        "prompt_version": "pod_design_brief_from_improvements_v001",
        "model": args.model,
        "brand_context_hash": stable_hash(brand_context),
        "campaign_row_hash": stable_hash(campaign_row),
        "product_entry_hash": stable_hash(product_entry),
        "sample_analysis_hash": stable_hash(sample_analysis),
        "improvement_points_hash": stable_hash(improvement_points),
    }
    cache = PodLLMOutputCache(brand_id=args.brand_id, namespace="design_brief_from_improvements")
    input_hash = cache.input_hash(cache_input)
    cached = cache.get(input_hash)
    if cached:
        brief = cached["output"]
        meta = {**cached.get("api_meta", {}), "cache_status": "hit", "cache_file": cached["cache_file"]}
    else:
        brief, meta = generate_design_brief(
            brand_context=brand_context,
            campaign_row=campaign_row,
            product_entry=product_entry,
            sample_analysis=sample_analysis,
            improvement_points=improvement_points,
            model=args.model,
        )
        cache_file = cache.set(input_hash=input_hash, output=brief, api_meta=meta, cache_input=cache_input)
        meta = {**meta, "cache_status": "miss_stored", "cache_file": str(cache_file), "input_hash": input_hash}
    final_prompt = build_final_prompt(brief)

    headers = [str(value).strip() for value in source["campaign_worksheet"].row_values(3)]
    header_map = {header: index + 1 for index, header in enumerate(headers) if header}
    source["campaign_worksheet"].update_cell(target["row_number"], header_map[final_prompt_column], final_prompt)

    report = {
        "status": "success",
        "brand_id": args.brand_id,
        "spreadsheet_title": source["spreadsheet_title"],
        "campaign_tab": source["campaign_tab"],
        "row_number": target["row_number"],
        "analysis_column": analysis_column,
        "improvements_column": improvements_column,
        "final_prompt_column": final_prompt_column,
        "campaign_name": campaign_row.get("campaign_name"),
        "brief": brief,
        "final_prompt": final_prompt,
        "api_meta": meta,
        "cost_estimate": estimate_cost_usd(args.model, meta.get("usage") or {}),
    }
    if not args.telegram_disabled:
        report["telegram_notification"] = notify_result(report)
    output_path = write_json(args.output_file, report)
    print(json.dumps({"status": "success", "report_file": str(output_path), "row_number": target["row_number"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
