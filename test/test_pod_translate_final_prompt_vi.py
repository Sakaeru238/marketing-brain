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
from core.services.pod_cache_service import PodLLMOutputCache, stable_hash
from core.services.pod_input_resolver import PodInputResolver
from core.services.pod_pipeline_utils import read_json, write_json

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = "claude-sonnet-4-6"


def extract_text(response_payload: dict[str, Any]) -> str:
    return "\n".join(
        block.get("text", "")
        for block in response_payload.get("content", []) or []
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def estimate_cost_usd(model: str, usage: dict[str, Any], *, cache_hit: bool = False) -> dict[str, Any]:
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


def translate_to_vi(*, final_prompt: str, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")
    user = {
        "task": "Translate the final design prompt to Vietnamese.",
        "rules": [
            "Keep the original structure and headings.",
            "Translate naturally into Vietnamese for a designer/operator.",
            "Preserve technical POD/design terms when useful, with Vietnamese explanation if needed.",
            "Do not add new design ideas. Do not omit details.",
            "Return plain text only, no markdown fence.",
        ],
        "final_prompt": final_prompt,
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
            "max_tokens": 9000,
            "temperature": 0.0,
            "system": "You are a precise Vietnamese translator for apparel design production prompts.",
            "messages": [{"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
        },
        timeout=240,
    )
    response.raise_for_status()
    raw = response.json()
    return {"translation": extract_text(raw)}, {
        "provider": "anthropic",
        "model": model,
        "response_id": raw.get("id"),
        "usage": raw.get("usage") or {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test: translate POD final prompt to Vietnamese.")
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--row-number", type=int, default=4)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-file", default="performance/test_results/pod_final_prompt_vi_translation_report.json")
    args = parser.parse_args()

    schema = read_json(GLOBAL_CONFIG_DIR / "gsheet_schema.json")["modules"]["pod_campaign"]
    fields = schema["campaign_intake"]["field_mappings"]
    source = PodInputResolver()._load_campaign_source(args.brand_id)
    ws = source["campaign_worksheet"]
    headers = [str(value).strip() for value in ws.row_values(3)]
    header_map = {header: index + 1 for index, header in enumerate(headers) if header}
    final_col = fields["final_prompt_from_sample"]
    vi_col = fields["final_prompt_vi"]
    final_prompt = ws.cell(args.row_number, header_map[final_col]).value or ""
    if not final_prompt.strip():
        raise ValueError("final prompt is empty")

    cache_input = {
        "prompt_version": "final_prompt_vi_translation_v001",
        "model": args.model,
        "target_language": "vi",
        "final_prompt_hash": stable_hash(final_prompt),
    }
    cache = PodLLMOutputCache(brand_id=args.brand_id, namespace="final_prompt_vi_translation")
    input_hash = cache.input_hash(cache_input)
    cached = cache.get(input_hash)
    if cached:
        result = cached["output"]
        meta = {**cached.get("api_meta", {}), "cache_status": "hit", "cache_file": cached["cache_file"]}
    else:
        result, meta = translate_to_vi(final_prompt=final_prompt, model=args.model)
        cache_file = cache.set(input_hash=input_hash, output=result, api_meta=meta, cache_input=cache_input)
        meta = {**meta, "cache_status": "miss_stored", "cache_file": str(cache_file), "input_hash": input_hash}

    ws.update_cell(args.row_number, header_map[vi_col], result["translation"])
    report = {
        "status": "success",
        "brand_id": args.brand_id,
        "row_number": args.row_number,
        "source_column": final_col,
        "target_column": vi_col,
        "chars_source": len(final_prompt),
        "chars_translation": len(result["translation"]),
        "api_meta": meta,
        "cost_estimate": estimate_cost_usd(args.model, meta.get("usage") or {}, cache_hit=meta.get("cache_status") == "hit"),
    }
    path = write_json(args.output_file, report)
    print(json.dumps({"status": "success", "report_file": str(path), "cache_status": meta.get("cache_status")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
