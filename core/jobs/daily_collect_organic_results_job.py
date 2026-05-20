from dotenv import load_dotenv
load_dotenv()

import json
import os
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.learning.organic_learning_memory_store import OrganicLearningMemoryStore
from core.notifications.telegram_notifier import TelegramNotifier
from core.publishers.facebook_graph_client import FacebookGraphClient
from core.services.organic_results_learning_service import OrganicResultsLearningService


# Meta deprecated older impressions/reach post metrics in late 2025 and introduced
# media-view based replacements. The parser accepts both modern and legacy names so
# the collector remains compatible across eligible Graph API metric profiles.
REQUIRED_INSIGHT_TARGETS = {"impressions", "reach", "clicks"}
INSIGHT_METRIC_NAME_TO_TARGET = {
    # Modern Page Post Media View metrics
    "post_media_view": "impressions",
    "post_total_media_view_unique": "reach",
    # Legacy Page Post Impression metrics, kept for compatibility if a route/app still returns them
    "post_impressions": "impressions",
    "post_impressions_unique": "reach",
    # Engagement metric that remains click-count based
    "post_clicks": "clicks",
}


def _clean_str(value) -> str:
    return str(value or "").strip()


def _normalize_facebook_post_url(url: str) -> str:
    """
    Keep the Facebook permalink/photo URL usable, but remove the redundant
    `type=3` query parameter before exporting to Organic_Results.
    """
    raw = _clean_str(url)
    if not raw or raw == "-":
        return "-"

    parts = urlsplit(raw)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    cleaned_items = [
        (key, value)
        for key, value in query_items
        if not (key == "type" and value == "3")
    ]
    cleaned_query = urlencode(cleaned_items, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, cleaned_query, parts.fragment))


def _as_int(value, default=0) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return default


def _summary_total(container: Dict, field: str) -> int:
    payload = container.get(field) or {}
    summary = payload.get("summary") or {}
    return _as_int(summary.get("total_count", 0))


def _share_count(container: Dict) -> int:
    payload = container.get("shares") or {}
    return _as_int(payload.get("count", 0))


def _parse_insights(insight_payload: Dict) -> Dict[str, int]:
    """
    Parse whatever Page Post insight metrics Meta returns.

    Do not fail a whole result row just because one of reach/impressions/clicks is missing.
    The downstream sheet uses "-" for unavailable metrics while preserving any metric that is present.
    """
    found = {}
    for item in insight_payload.get("data", []) or []:
        name = _clean_str(item.get("name"))
        values = item.get("values") or []
        value = None
        if values:
            first = values[0] or {}
            value = first.get("value")
        target = INSIGHT_METRIC_NAME_TO_TARGET.get(name)
        if target:
            found[target] = _as_int(value, 0)

    missing = [target for target in REQUIRED_INSIGHT_TARGETS if target not in found]
    if missing:
        found["_missing_targets"] = missing
    found["_metric_profile"] = insight_payload.get("_metric_profile", "")
    found["_metric_request_mode"] = insight_payload.get("_metric_request_mode", "")
    return found


def _engagement_rate(likes: int, comments: int, shares: int, clicks: int, reach: int) -> float:
    if reach <= 0:
        return 0.0
    return round(((likes + comments + shares + clicks) / reach) * 100, 4)


def _results_date() -> str:
    timezone_name = os.getenv("RESULTS_DATE_TIMEZONE", "Asia/Ho_Chi_Minh")
    return datetime.now(ZoneInfo(timezone_name)).date().isoformat()


def _collected_at() -> str:
    timezone_name = os.getenv("RESULTS_DATE_TIMEZONE", "Asia/Ho_Chi_Minh")
    return datetime.now(ZoneInfo(timezone_name)).isoformat()


def _is_active(value) -> bool:
    return _clean_str(value).lower() == "active"


def _is_facebook_row(row: Dict) -> bool:
    return _clean_str(row.get("platform_id")).lower() == "facebook"


def _parse_iso_datetime(value):
    raw = _clean_str(value)
    if not raw:
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _is_posted_status(row: Dict) -> bool:
    return _clean_str(row.get("post_status")).lower() == "posted"


def _page_context_for_row(row: Dict, page_context_by_key: Dict[Tuple[str, str, str], Dict]) -> Dict:
    brand_id = _clean_str(row.get("brand_id"))
    page_id = _clean_str(row.get("page_id"))
    page_url = _clean_str(row.get("page_url"))
    platform_id = _clean_str(row.get("platform_id"))

    lookup_keys = [
        (brand_id, page_id, platform_id),
        (brand_id, page_id, ""),
        (brand_id, page_url, platform_id),
        (brand_id, page_url, ""),
    ]
    for key in lookup_keys:
        if key in page_context_by_key:
            return page_context_by_key[key]
    return {}


def _zoneinfo_or_utc(timezone_name: str):
    try:
        return ZoneInfo(timezone_name or "UTC")
    except Exception:
        return timezone.utc


def _is_next_calendar_day_for_results(row: Dict, page_context_by_key: Dict[Tuple[str, str, str], Dict]) -> bool:
    """
    Collect only after the calendar day of the post has passed.

    Rule:
    - Prefer the target market timezone from Campaign_Config.target_timezone.
    - Fall back to UTC if the page timezone is unavailable/invalid.
    - A post published/scheduled on local date D is collectable once current local date > D.

    This intentionally replaces the previous strict "age >= 24 hours" rule.
    """
    reference_dt = (
        _parse_iso_datetime(row.get("published_or_scheduled_at"))
        or _parse_iso_datetime(row.get("scheduled_datetime_utc"))
    )
    if reference_dt is None:
        return False

    page_context = _page_context_for_row(row, page_context_by_key)
    target_timezone = _clean_str(page_context.get("target_timezone")) or "UTC"
    tz = _zoneinfo_or_utc(target_timezone)

    post_local_date = reference_dt.astimezone(tz).date()
    today_local_date = datetime.now(tz).date()
    return today_local_date > post_local_date


def _is_collectable_post(row: Dict, page_context_by_key: Dict[Tuple[str, str, str], Dict]) -> bool:
    facebook_post_id = _clean_str(row.get("facebook_post_id"))
    if not facebook_post_id or facebook_post_id.lower().startswith("dryrun_"):
        return False
    if not _is_facebook_row(row):
        return False
    if not _is_posted_status(row):
        return False
    if not _is_next_calendar_day_for_results(row, page_context_by_key):
        return False
    return True


def _page_context_index(exporter: GoogleSheetsExporter, spreadsheet, route: Dict) -> Dict[Tuple[str, str, str], Dict]:
    pages_tab = exporter._organic_tab_name(route, "pages")
    ws = spreadsheet.worksheet(pages_tab)
    rows = exporter._worksheet_records(ws)
    indexed = {}
    for row in rows:
        row = exporter.normalize_page_channel_record(row)
        brand_id = _clean_str(row.get("brand_id"))
        page_id = _clean_str(row.get("page_id"))
        page_url = _clean_str(row.get("page_url"))
        platform_id = _clean_str(row.get("platform_id"))
        if brand_id and page_id:
            indexed[(brand_id, page_id, platform_id)] = row
            indexed[(brand_id, page_id, "")] = row
        if brand_id and page_url:
            indexed[(brand_id, page_url, platform_id)] = row
            indexed[(brand_id, page_url, "")] = row
    return indexed


def _insight_value(insights: Dict, key: str):
    value = insights.get(key, "-")
    if value in (None, ""):
        return "-"
    if str(value).strip() == "-":
        return "-"
    return _as_int(value)


def _metric_or_none(value):
    if value in (None, ""):
        return None
    if str(value).strip() == "-":
        return None
    return _as_int(value)


def _computed_engagement_rate(likes, comments, shares, clicks, reach, impressions):
    """
    Engagement rate rule:
    - Sum only available engagement metrics in the numerator.
    - Priority denominator: reach, then impressions.
    - If no valid denominator exists, return "-".
    - If all numerator engagement metrics are unavailable, return "-".

    For Facebook currently likes/comments/shares are usually available; clicks may be "-".
    """
    numerator_components = [
        _metric_or_none(likes),
        _metric_or_none(comments),
        _metric_or_none(shares),
        _metric_or_none(clicks),
    ]
    available_components = [value for value in numerator_components if value is not None]
    if not available_components:
        return "-"

    denominator = _metric_or_none(reach)
    if denominator is None or denominator <= 0:
        denominator = _metric_or_none(impressions)
    if denominator is None or denominator <= 0:
        return "-"

    return round((sum(available_components) / denominator) * 100, 4)


def _build_result_record(row: Dict, content: Dict, insights: Dict[str, int]) -> Dict:
    likes = _summary_total(content, "likes")
    comments = _summary_total(content, "comments")
    shares = _share_count(content)
    reach = _insight_value(insights, "reach")
    impressions = _insight_value(insights, "impressions")
    clicks = _insight_value(insights, "clicks")

    # `post_url` must be the actual Page Post permalink.
    # For photo objects, FacebookGraphClient resolves Photo.page_story_id -> Page Post.permalink_url.
    # Do NOT use Photo.link here because it is not the canonical post URL.
    url = _normalize_facebook_post_url(content.get("permalink_url") or "-")
    return {
        "campaign_id": row.get("campaign_id", ""),
        "organic_run_id": row.get("organic_run_id", ""),
        "date": _results_date(),
        "post_id": row.get("post_id", ""),
        "brand_id": row.get("brand_id", ""),
        "niche_id": row.get("niche_id", ""),
        "page_id": row.get("page_id", ""),
        "page_url": row.get("page_url", ""),
        "platform_id": row.get("platform_id", ""),
        "facebook_post_id": row.get("facebook_post_id", ""),
        "published_date": content.get("created_time", ""),
        "post_url": url,
        "content_archetype": row.get("content_archetype", ""),
        "interaction_trigger_type": row.get("interaction_trigger_type", ""),
        "target_human": row.get("target_human", ""),
        "core_problem": row.get("core_problem", ""),
        "desired_post_outcome": row.get("desired_post_outcome", ""),
        "desired_action": row.get("desired_action", ""),
        "content_tags": row.get("content_tags", ""),
        "seo_keywords_used": row.get("seo_keywords_used", ""),
        "recommended_posting_window": row.get("recommended_posting_window", ""),
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": "-",
        "reach": reach,
        "impressions": impressions,
        "clicks": clicks,
        "follows": "-",
        "engagement_rate": _computed_engagement_rate(likes, comments, shares, clicks, reach, impressions),
        # Preserve notes if they already exist in the sheet; exporter only updates passed fields.
        "ai_result_summary": "",
        "ai_learning": "",
        "ai_next_action": "",
        "collected_at": _collected_at(),
        # Pass-through fields used by AI learning layer but not exported unless headers exist.
        "content_role": row.get("content_role", ""),
        "content_pillar": row.get("content_pillar", ""),
        "hook_type": row.get("hook_type", ""),
        "hook": row.get("hook", ""),
        "post_format": row.get("post_format", ""),
        "product_mention_level": row.get("product_mention_level", ""),
    }


def _collect_route(exporter: GoogleSheetsExporter, route: Dict) -> Dict:
    spreadsheet = exporter._open_spreadsheet_for_route(route)
    posts_tab = exporter._organic_tab_name(route, "posts")
    posts_ws = spreadsheet.worksheet(posts_tab)
    post_rows = exporter._worksheet_records(posts_ws)
    page_context_by_key = _page_context_index(exporter, spreadsheet, route)

    max_posts_raw = _clean_str(os.getenv("ORGANIC_RESULTS_MAX_POSTS"))
    max_posts = int(max_posts_raw) if max_posts_raw else None

    candidates = [row for row in post_rows if _is_collectable_post(row, page_context_by_key)]
    if max_posts is not None:
        candidates = candidates[:max_posts]

    graph_clients: Dict[str, FacebookGraphClient] = {}
    collected = []
    row_errors = []

    for row in candidates:
        facebook_post_id = _clean_str(row.get("facebook_post_id"))
        try:
            brand_id = _clean_str(row.get("brand_id"))
            page_id = _clean_str(row.get("page_id"))
            platform_id = _clean_str(row.get("platform_id"))
            page_context = (
                page_context_by_key.get((brand_id, page_id, platform_id))
                or page_context_by_key.get((brand_id, page_id, ""))
                or {}
            )
            private_page_id = _clean_str(page_context.get("private_page_id"))
            page_access_token = _clean_str(page_context.get("token"))
            if not private_page_id:
                raise ValueError(
                    "Campaign_Config.private_page_id is required for organic result collection. "
                    f"brand_id={brand_id}, page_id={page_id}, platform_id={platform_id}"
                )
            if not page_access_token:
                raise ValueError(
                    "Campaign_Config.token is required for organic result collection. "
                    f"brand_id={brand_id}, page_id={page_id}, platform_id={platform_id}"
                )
            graph_key = f"{private_page_id}|{page_access_token}"
            graph_client = graph_clients.setdefault(
                graph_key,
                FacebookGraphClient(page_id=private_page_id, page_access_token=page_access_token),
            )
            content = graph_client.get_content_details(facebook_post_id)
            insights_object_id = _clean_str(content.get("_insights_object_id")) or facebook_post_id
            try:
                insight_payload = graph_client.get_post_insights(insights_object_id)
                insights = _parse_insights(insight_payload)
            except Exception as insight_exc:
                # Facebook Post/Photo objects can be valid and collectable even when
                # Page Post Insights metrics are unavailable for that object/token/version.
                # Do not fail the whole result row; keep the post-level metrics and mark
                # insight-only columns as unavailable for Facebook.
                insights = {
                    "reach": "-",
                    "impressions": "-",
                    "clicks": "-",
                    "_insights_error": str(insight_exc),
                }
            collected.append(_build_result_record(row, content, insights))
        except Exception as exc:
            row_errors.append({
                "post_id": row.get("post_id", ""),
                "facebook_post_id": facebook_post_id,
                "error": str(exc),
            })

    learning_service = OrganicResultsLearningService()
    learned_results, daily_logs = learning_service.enrich_results_and_build_daily_logs(
        results=collected,
        page_context_by_key=page_context_by_key,
    )

    results_export = exporter.upsert_organic_results(route, learned_results)
    learning_export = exporter.upsert_daily_learning_logs(route, daily_logs)
    memory_summary = OrganicLearningMemoryStore().upsert_from_results(learned_results)

    return {
        "route": {
            "brand_id": route.get("brand_id", ""),
            "page_id": route.get("page_id", ""),
            "platform_id": route.get("platform_id", ""),
            "sheet": route.get("google_sheet_url", ""),
        },
        "candidates": len(candidates),
        "collected": len(collected),
        "row_errors": row_errors,
        "organic_results_export": results_export,
        "daily_learning_export": learning_export,
        "local_learning_memory": memory_summary,
    }


def main():
    notifier = TelegramNotifier()
    exporter = GoogleSheetsExporter()

    active_routes = [route for route in exporter.routes if _is_active(route.get("status", "active"))]
    outputs = []
    errors = []

    for route in active_routes:
        try:
            outputs.append(_collect_route(exporter, route))
        except Exception as exc:
            errors.append({
                "brand_id": route.get("brand_id", ""),
                "page_id": route.get("page_id", ""),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })

    total_collected = sum(item.get("collected", 0) for item in outputs)
    total_row_errors = sum(len(item.get("row_errors", [])) for item in outputs)

    notifier.send(
        "📊 Organic results collector finished\n"
        f"Routes: {len(active_routes)}\n"
        f"Rows collected: {total_collected}\n"
        f"Row errors: {total_row_errors}\n"
        f"Route errors: {len(errors)}\n"
        "Outputs updated: Organic_Results, Daily_Learning_Log, local organic_learning JSONL."
    )

    print(json.dumps({
        "status": "finished" if not errors else "finished_with_route_errors",
        "routes_processed": len(active_routes),
        "total_collected": total_collected,
        "total_row_errors": total_row_errors,
        "outputs": outputs,
        "errors": errors,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
