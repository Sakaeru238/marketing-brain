from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config.paths import GLOBAL_CONFIG_DIR
from core.notifications.telegram_notifier import TelegramNotifier
from core.services.pod_cache_service import PodLLMOutputCache, stable_hash
from core.services.pod_input_resolver import PodInputResolver
from core.services.pod_pipeline_utils import read_json, safe_name, write_json

load_dotenv(PROJECT_ROOT / ".env")


STEP_NAME = "test_pod_sample_image_analysis"
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


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta: dict[str, str] = {}
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() != "meta":
            return
        key = values.get("property") or values.get("name")
        content = values.get("content")
        if key and content:
            self.meta[key] = content

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()


def load_schema() -> dict[str, Any]:
    payload = read_json(GLOBAL_CONFIG_DIR / "gsheet_schema.json")
    return payload["modules"]["pod_campaign"]


def google_drive_download_url(url: str) -> str | None:
    match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
    if not match:
        match = re.search(r"[?&]id=([^&]+)", url)
    if not match:
        return None
    return f"https://drive.google.com/uc?export=download&id={match.group(1)}"


def cache_reference_image(*, brand_id: str, campaign_id: str, content_type: str, image_bytes: bytes) -> dict[str, str]:
    extension = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(content_type, ".img")
    image_hash = stable_hash(
        {
            "content_type": content_type,
            "sha256": __import__("hashlib").sha256(image_bytes).hexdigest(),
        }
    )
    path = (
        PROJECT_ROOT
        / "data"
        / "brands"
        / brand_id
        / "pod"
        / "campaigns"
        / safe_name(campaign_id)
        / "00_inputs"
        / "reference_images"
        / f"{image_hash}{extension}"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(image_bytes)
    return {"image_hash": image_hash, "local_image_file": str(path)}


def fetch_image_url(url: str) -> dict[str, Any] | None:
    response = requests.get(
        url,
        headers={"user-agent": "Mozilla/5.0 marketing-brain sample image analysis test"},
        timeout=30,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        return None
    return {
        "source_url": url,
        "content_type": content_type,
        "image_bytes": response.content,
        "reference_context": {
            "kind": "direct_image",
            "source_url": url,
        },
    }


def fetch_reference(url: str, *, brand_id: str, campaign_id: str) -> dict[str, Any]:
    if not url:
        raise ValueError("Sample image URL is empty.")
    drive_url = google_drive_download_url(url)
    if drive_url:
        try:
            fetched = fetch_image_url(drive_url)
            if fetched:
                image_cache = cache_reference_image(
                    brand_id=brand_id,
                    campaign_id=campaign_id,
                    content_type=fetched["content_type"],
                    image_bytes=fetched["image_bytes"],
                )
                fetched["source_url"] = url
                fetched["reference_context"] = {
                    "kind": "google_drive_image",
                    "source_url": url,
                    "download_url": drive_url,
                    **image_cache,
                }
                return fetched
        except Exception as exc:
            drive_fetch_error = str(exc)
        else:
            drive_fetch_error = "Google Drive download URL did not return image content."
    else:
        drive_fetch_error = ""

    try:
        response = requests.get(
            url,
            headers={"user-agent": "Mozilla/5.0 marketing-brain sample image analysis test"},
            timeout=30,
        )
        response.raise_for_status()
    except Exception as exc:
        return {
            "source_url": url,
            "content_type": "",
            "image_bytes": None,
            "reference_context": {
                "kind": "url_unavailable",
                "source_url": url,
                "fetch_error": str(exc),
                "drive_fetch_error": drive_fetch_error,
            },
        }
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()

    if content_type.startswith("image/"):
        image_cache = cache_reference_image(
            brand_id=brand_id,
            campaign_id=campaign_id,
            content_type=content_type,
            image_bytes=response.content,
        )
        return {
            "source_url": url,
            "content_type": content_type,
            "image_bytes": response.content,
            "reference_context": {
                "kind": "direct_image",
                "source_url": url,
                **image_cache,
            },
        }

    parser = MetadataParser()
    parser.feed(response.text[:200_000])
    image_url = (
        parser.meta.get("og:image")
        or parser.meta.get("twitter:image")
        or parser.meta.get("twitter:image:src")
        or ""
    )
    reference_context = {
        "kind": "webpage",
        "source_url": url,
        "page_title": parser.meta.get("og:title") or parser.title,
        "page_description": parser.meta.get("og:description") or parser.meta.get("description") or "",
        "candidate_image_url": image_url,
        "drive_fetch_error": drive_fetch_error,
    }
    if image_url:
        try:
            image_response = requests.get(
                image_url,
                headers={"user-agent": "Mozilla/5.0 marketing-brain sample image analysis test"},
                timeout=30,
            )
            image_response.raise_for_status()
            image_type = image_response.headers.get("content-type", "").split(";")[0].strip().lower()
            if image_type.startswith("image/"):
                image_cache = cache_reference_image(
                    brand_id=brand_id,
                    campaign_id=campaign_id,
                    content_type=image_type,
                    image_bytes=image_response.content,
                )
                return {
                    "source_url": url,
                    "content_type": image_type,
                    "image_bytes": image_response.content,
                    "reference_context": {**reference_context, **image_cache},
                }
        except Exception as exc:
            reference_context["candidate_image_fetch_error"] = str(exc)

    return {
        "source_url": url,
        "content_type": content_type,
        "image_bytes": None,
        "reference_context": reference_context,
    }


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


def fallback_structured_response(text: str) -> dict[str, str]:
    analysis_marker = '"sample_image_analysis"'
    improvements_marker = '"sample_image_improvement_points"'
    if analysis_marker not in text or improvements_marker not in text:
        raise ValueError("Claude response did not contain expected output keys.")
    before, after = text.split(improvements_marker, 1)
    analysis = before.split(analysis_marker, 1)[1]
    analysis = analysis.split(":", 1)[1].strip().strip('",{} \n')
    improvements = after.split(":", 1)[1].strip().strip('",{} \n')
    return {
        "sample_image_analysis": analysis,
        "sample_image_improvement_points": improvements,
    }


def analyze_sample(
    *,
    brand_context: dict[str, Any],
    campaign_row: dict[str, Any],
    product_entry: dict[str, Any],
    reference: dict[str, Any],
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required.")

    system = (
        "You combine julianoczkowski/designer-skills visual analysis with Alysha creative strategy. "
        "First, analyze the reference design/composition objectively. "
        "Second, propose improvements that fit the brand intake, team_or_fanbase_focus, "
        "sku_product_type, and product catalog. Return JSON only."
    )
    user_text = {
        "task": "Analyze sample image/design and propose improvements for the POD campaign row.",
        "required_output": {
            "sample_image_analysis": (
                "Write this for the Google Sheet column 'phân tích ảnh mẫu'. "
                "Only analyze the sample shirt design itself. Focus on overall composition, presentation style, "
                "patterns, decorative motifs, line work, color system, visual hierarchy, and the exact placement "
                "of main parts such as logo, central text, supporting text, artwork blocks, trims, collar/sleeve "
                "details, and background/fabric areas. "
                "Do not use team_or_fanbase_focus, brand strategy, or campaign positioning in this section."
            ),
            "sample_image_improvement_points": (
                "Write this for the Google Sheet column 'điểm cải tiến so với ảnh mẫu'. "
                "This section must use team_or_fanbase_focus, brand context, sku_product_type, "
                "campaign constraints, and product catalog to propose campaign-fit improvements."
            ),
        },
        "reference_context": reference["reference_context"],
        "brand_context": brand_context,
        "campaign_fields": {
            "campaign_name": campaign_row.get("campaign_name"),
            "team_or_fanbase_focus": campaign_row.get("team_or_fanbase_focus"),
            "sku_product_type": campaign_row.get("sku_product_type"),
            "campaign_goal": campaign_row.get("campaign_goal"),
            "creative_seed_idea": campaign_row.get("creative_seed_idea"),
            "must_keep_elements": campaign_row.get("must_keep_elements"),
            "must_avoid_elements": campaign_row.get("must_avoid_elements"),
            "required_output_types": campaign_row.get("required_output_types"),
        },
        "product_catalog_entry": product_entry,
        "rules": [
            "Strict separation: sample_image_analysis is objective sample-only analysis.",
            "Strict separation: sample_image_improvement_points is where brand, team_or_fanbase_focus, and SKU fit are applied.",
            "For sample_image_analysis, do not say what the campaign should do; describe what the sample image currently does.",
            "Do not recommend official team logos, official NFL marks, or trademark copying.",
            "Keep improvements practical for POD execution.",
            "Mention composition, hierarchy, color, typography/symbol system, product placement, and brand/IP safety.",
            "If only webpage metadata is available, clearly base the analysis on visible metadata/reference context.",
        ],
    }

    content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(user_text, ensure_ascii=False)}]
    image_bytes = reference.get("image_bytes")
    content_type = reference.get("content_type") or ""
    if image_bytes and content_type.startswith("image/"):
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": content_type,
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                },
            }
        )

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 3600,
            "temperature": 0.2,
            "system": system,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=180,
    )
    response.raise_for_status()
    raw = response.json()
    response_text = extract_text(raw)
    try:
        parsed = parse_json_response(response_text)
    except Exception:
        parsed = fallback_structured_response(response_text)
        parsed["_parse_warning"] = "Claude response was not valid JSON; parsed with fallback markers."
    return parsed, {
        "provider": "anthropic",
        "model": model,
        "response_id": raw.get("id"),
        "usage": raw.get("usage") or {},
        "raw_text_saved": False,
        "reference_content_type": reference.get("content_type"),
        "reference_context": reference.get("reference_context"),
    }


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


def notify_result(report: dict[str, Any]) -> dict[str, Any]:
    cost = report["cost_estimate"]
    message = (
        "POD sample image analysis test completed\n"
        f"Brand: {report['brand_id']}\n"
        f"Row: {report['row_number']}\n"
        f"Model: {report['api_meta']['model']}\n"
        f"Input tokens: {cost['input_tokens']}\n"
        f"Output tokens: {cost['output_tokens']}\n"
        f"Total tokens: {cost['total_tokens']}\n"
        f"Estimated cost: ${cost['total_cost_usd']:.6f}\n"
        f"Reference kind: {report['api_meta']['reference_context'].get('kind')}"
    )
    return TelegramNotifier().send(message)


def find_target_row(source: dict[str, Any], sample_column: str, row_number: int | None) -> dict[str, Any]:
    for item in source["campaign_rows"]:
        if row_number and item["row_number"] != row_number:
            continue
        if str(item["data"].get(sample_column) or "").strip():
            return item
    raise ValueError(f"No campaign row found with non-empty sample column: {sample_column}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual test: analyze POD sample image and update campaign GSheet.")
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--row-number", type=int, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output-file", default="performance/test_results/pod_sample_image_analysis_test.json")
    parser.add_argument("--telegram-disabled", action="store_true")
    args = parser.parse_args()

    schema = load_schema()
    mappings = schema["campaign_intake"]["field_mappings"]
    sample_column = mappings["sample_image_url"]
    analysis_column = mappings["sample_image_analysis"]
    improvements_column = mappings["sample_image_improvement_points"]

    resolver = PodInputResolver()
    source = resolver._load_campaign_source(args.brand_id)
    target = find_target_row(source, sample_column, args.row_number)
    campaign_row = target["data"]
    campaign_id = safe_name(campaign_row.get("campaign_id") or campaign_row.get("campaign_name") or f"row_{target['row_number']}")
    product_entry = resolver._find_product_entry(
        product_rows=source["product_rows"],
        schema=source["schema"],
        product_ref_id=campaign_row.get("product_ref_id"),
    )

    brand_paths = resolver.context_resolver.resolve(args.brand_id)
    brand_context = read_json(brand_paths["brand_context_json_file"])

    reference = fetch_reference(campaign_row[sample_column], brand_id=args.brand_id, campaign_id=campaign_id)
    cache_input = {
        "prompt_version": "pod_sample_image_analysis_v002",
        "model": args.model,
        "sample_url": campaign_row[sample_column],
        "reference_context": reference["reference_context"],
        "campaign_fields": {
            key: campaign_row.get(key, "")
            for key in [
                "campaign_name",
                "team_or_fanbase_focus",
                "sku_product_type",
                "campaign_goal",
                "creative_seed_idea",
                "must_keep_elements",
                "must_avoid_elements",
                "required_output_types",
            ]
        },
        "product_entry": product_entry,
        "brand_context_hash": stable_hash(brand_context),
    }
    cache = PodLLMOutputCache(brand_id=args.brand_id, namespace="sample_image_analysis")
    input_hash = cache.input_hash(cache_input)
    cached = cache.get(input_hash)
    if cached:
        result = cached["output"]
        meta = {**cached.get("api_meta", {}), "cache_status": "hit", "cache_file": cached["cache_file"]}
    else:
        result, meta = analyze_sample(
            brand_context=brand_context,
            campaign_row=campaign_row,
            product_entry=product_entry,
            reference=reference,
            model=args.model,
        )
        cache_file = cache.set(input_hash=input_hash, output=result, api_meta=meta, cache_input=cache_input)
        meta = {**meta, "cache_status": "miss_stored", "cache_file": str(cache_file), "input_hash": input_hash}

    headers = [str(value).strip() for value in source["campaign_worksheet"].row_values(3)]
    header_map = {header: index + 1 for index, header in enumerate(headers) if header}
    updates = [
        {
            "range": rowcol_to_a1(target["row_number"], header_map[analysis_column]),
            "values": [[result["sample_image_analysis"]]],
        },
        {
            "range": rowcol_to_a1(target["row_number"], header_map[improvements_column]),
            "values": [[result["sample_image_improvement_points"]]],
        },
    ]
    source["campaign_worksheet"].batch_update(updates, value_input_option="USER_ENTERED")

    report = {
        "status": "success",
        "brand_id": args.brand_id,
        "spreadsheet_title": source["spreadsheet_title"],
        "campaign_tab": source["campaign_tab"],
        "row_number": target["row_number"],
        "sample_column": sample_column,
        "analysis_column": analysis_column,
        "improvements_column": improvements_column,
        "sample_url": campaign_row[sample_column],
        "result": result,
        "api_meta": meta,
        "cost_estimate": estimate_cost_usd(args.model, meta.get("usage") or {}),
    }
    if not args.telegram_disabled:
        report["telegram_notification"] = notify_result(report)
    output_path = write_json(args.output_file, report)
    print(json.dumps({"status": "success", "report_file": str(output_path), "row_number": target["row_number"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
