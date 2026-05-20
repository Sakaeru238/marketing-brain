"""
Production job: publish ready organic posts to Facebook from Google Sheet Organic_Posts.

Rules:
  - Process only rows where post_status == "ready".
  - Map Organic_Posts to Campaign_Config by brand_id + public page id/page_url.
    The real Facebook Page ID used by Meta API is Campaign_Config.private_page_id.
  - If scheduled_datetime_utc is blank, compute a schedule time from the target
    audience timezone in Campaign_Config.target_timezone.
  - The machine can run in any timezone, including Vietnam; all scheduling math
    uses timezone-aware UTC + the target market timezone, never local machine time.
  - After successful scheduling/publishing, update post_status -> "posted".
  - If validation/publish/job error happens, update post_status -> "error".
  - Send a Telegram notification after each processed row.

Important write behavior:
  - This job updates only job-control/publisher fields, plus scheduled_datetime_utc
    only when it was blank and the job calculated it.
  - It never rewrites content fields such as post_text, image_url, hook, caption,
    content_pillar, notes_user, etc.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import json
import os
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.notifications.telegram_notifier import TelegramNotifier
from core.services.facebook_page_publisher_service import FacebookPagePublisherService
from core.utils.organic_gsheet_schema import (
    organic_post_status_values,
    organic_publish_job_config,
    organic_status_list,
)


def _required_config_list(config: Dict[str, Any], key: str) -> List[str]:
    values = config.get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"Missing organic publish job config list: {key}")
    return [str(value).strip() for value in values if str(value).strip()]


def _parse_time_slots(values: List[str]) -> List[time]:
    slots = []
    for value in values:
        hour, minute = str(value).strip().split(":", 1)
        slots.append(time(int(hour), int(minute)))
    return slots


PUBLISH_JOB_CONFIG = organic_publish_job_config()
SCHEDULE_POLICY = PUBLISH_JOB_CONFIG.get("schedule_policy") or {}

REQUIRED_POST_COLUMNS = _required_config_list(PUBLISH_JOB_CONFIG, "required_post_columns")
REQUIRED_PAGE_COLUMNS = _required_config_list(PUBLISH_JOB_CONFIG, "required_page_columns")

ORGANIC_STATUS_VALUES = organic_post_status_values()
TARGET_PLATFORM_ID = str(PUBLISH_JOB_CONFIG["target_platform_id"])
READY_POST_STATUS = str(ORGANIC_STATUS_VALUES["ready_post_status"])
SUCCESS_POST_STATUS = str(ORGANIC_STATUS_VALUES["success_post_status"])
ERROR_POST_STATUS = str(ORGANIC_STATUS_VALUES["error_post_status"])
JOB_ERROR_PUBLISHER_STATUS = str(ORGANIC_STATUS_VALUES["job_error_publisher_status"])

SUCCESS_PUBLISHER_STATUSES = set(organic_status_list("success_publisher_statuses"))
ERROR_PUBLISHER_STATUSES = set(organic_status_list("error_publisher_statuses"))

ALLOWED_UPDATE_COLUMNS = set(_required_config_list(PUBLISH_JOB_CONFIG, "allowed_update_columns"))
WEEKDAY_ENGAGEMENT_SLOTS = _parse_time_slots(_required_config_list(SCHEDULE_POLICY, "weekday_engagement_slots"))
WEEKEND_ENGAGEMENT_SLOTS = _parse_time_slots(_required_config_list(SCHEDULE_POLICY, "weekend_engagement_slots"))
MIN_FUTURE_MINUTES = int(SCHEDULE_POLICY["min_future_minutes"])
SLOT_SPACING_MINUTES = int(SCHEDULE_POLICY["slot_spacing_minutes"])
MAX_SEARCH_DAYS = int(SCHEDULE_POLICY["max_search_days"])
MARKET_TIMEZONE_FALLBACKS = {
    str(key).strip().lower(): str(value).strip()
    for key, value in (PUBLISH_JOB_CONFIG.get("market_timezone_fallbacks") or {}).items()
    if str(key).strip() and str(value).strip()
}


def _column_letter(index_1_based: int) -> str:
    result = ""
    n = index_1_based
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _header_map(headers: List[str]) -> Dict[str, int]:
    return {
        str(header).strip(): idx + 1
        for idx, header in enumerate(headers)
        if str(header).strip()
    }


def _rows_to_records(values: List[List[Any]], headers: List[str]) -> List[Tuple[int, Dict[str, Any]]]:
    records: List[Tuple[int, Dict[str, Any]]] = []
    clean_headers = [str(header).strip() for header in headers]

    for row_number, row_values in enumerate(values[1:], start=2):
        record: Dict[str, Any] = {}
        for col_idx, header in enumerate(clean_headers):
            if not header:
                continue
            record[header] = row_values[col_idx] if col_idx < len(row_values) else ""

        if any(str(value).strip() for value in record.values()):
            records.append((row_number, record))

    return records


def _ensure_required_columns(column_map: Dict[str, int], required: Iterable[str], sheet_name: str) -> None:
    missing = [col for col in required if col not in column_map]
    if missing:
        raise ValueError(f"{sheet_name} sheet is missing required columns: " + ", ".join(missing))


def _extract_facebook_post_id(result: Dict[str, Any]) -> str:
    fb_response = result.get("facebook_response", {}) or {}
    if not isinstance(fb_response, dict):
        return ""
    return str(fb_response.get("id") or fb_response.get("post_id") or "")


def _extract_error(result: Dict[str, Any]) -> str:
    if result.get("error"):
        return str(result.get("error"))
    errors = result.get("errors") or []
    if isinstance(errors, list):
        return "; ".join(str(error) for error in errors if error)
    return str(errors or "")


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc_datetime(value: str) -> datetime:
    value = str(value or "").strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _slot_times_for_date(local_date) -> List[time]:
    # Python weekday: Monday=0, Sunday=6
    if local_date.weekday() >= 5:
        return WEEKEND_ENGAGEMENT_SLOTS
    return WEEKDAY_ENGAGEMENT_SLOTS


def _normalize_market(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_url(value: str) -> str:
    """Normalize page URLs enough for route/Campaign_Config matching."""
    raw = str(value or "").strip()
    if not raw:
        return ""

    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().replace("www.", "")
    path = (parsed.path or "").strip("/").lower()
    return f"{host}/{path}" if path else host


def _urls_match(left: str, right: str) -> bool:
    return bool(_normalize_url(left)) and _normalize_url(left) == _normalize_url(right)


def _route_page_url(route: Dict[str, Any]) -> str:
    return str(
        route.get("page_url")
        or route.get("url")
        or route.get("URL")
        or route.get("facebook_page_url")
        or ""
    ).strip()


def _find_route_by_brand_page_url(exporter: GoogleSheetsExporter, *, brand_id: str, page_url: Optional[str], platform_id: Optional[str]) -> Dict[str, Any]:
    """
    Prefer route matching by brand_id + page_url + platform_id.

    Brand route owns the Google Sheet. Campaign_Config owns page metadata and
    the private Facebook Page ID used for publishing.
    """
    active_routes = [
        r for r in exporter.routes
        if str(r.get("status", "active")).strip().lower() == "active"
    ]

    if page_url:
        matches = [
            r for r in active_routes
            if str(r.get("brand_id", "")).strip() == str(brand_id).strip()
            and (not platform_id or str(r.get("platform_id", "")).strip().lower() == str(platform_id).strip().lower())
            and _urls_match(_route_page_url(r), page_url)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                "Multiple active Google Sheet routes match "
                f"brand_id={brand_id}, page_url={page_url}, platform_id={platform_id}."
            )

    # Fallback: allow the existing exporter logic only when it can resolve a unique
    # route by brand/platform.
    return exporter._find_route(brand_id=brand_id, page_id=None, platform_id=platform_id)


def _resolve_target_timezone(page_context: Dict[str, Any]) -> ZoneInfo:
    tz_name = str(page_context.get("target_timezone") or "").strip()
    if not tz_name:
        market = _normalize_market(page_context.get("market"))
        tz_name = MARKET_TIMEZONE_FALLBACKS.get(market, "")

    if not tz_name:
        raise ValueError(
            "target_timezone is required in Campaign_Config. "
            "Use an IANA timezone such as America/New_York, Europe/London, Asia/Ho_Chi_Minh."
        )

    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Invalid target_timezone '{tz_name}' in Campaign_Config. "
            "Use an IANA timezone such as America/New_York, Europe/London, Asia/Ho_Chi_Minh."
        ) from exc


def _load_page_context(
    spreadsheet,
    pages_tab: str,
    *,
    brand_id: str,
    page_id: str,
    page_url: str,
    platform_id: str,
) -> Dict[str, Any]:
    ws = spreadsheet.worksheet(pages_tab)
    values = ws.get_all_values()
    if not values:
        raise ValueError(f"{pages_tab} sheet is empty; expected a header row.")

    headers = values[0]
    column_map = _header_map(headers)
    _ensure_required_columns(column_map, REQUIRED_PAGE_COLUMNS, pages_tab)

    rows = _rows_to_records(values, headers)
    for _, row in rows:
        if not row.get("page_id") and row.get("public_page_id"):
            row["page_id"] = row.get("public_page_id")
        same_brand = str(row.get("brand_id", "")).strip() == str(brand_id).strip()
        same_page_id = bool(page_id) and str(row.get("public_page_id", "")).strip() == str(page_id).strip()
        same_page_url = bool(page_url) and _urls_match(str(row.get("page_url", "")), page_url)
        same_platform = str(row.get("platform_id", "")).strip().lower() == str(platform_id).strip().lower()
        if same_brand and same_platform and (same_page_id or same_page_url):
            return row

    raise ValueError(
        f"{pages_tab} row not found for brand_id={brand_id}, "
        f"page_id={page_id}, page_url={page_url}, platform_id={platform_id}. "
        "Mapping rule: Organic_Posts.brand_id + Organic_Posts.page_id/page_url "
        "must match Campaign_Config.brand_id + Campaign_Config.public_page_id/page_url. "
        "The real Facebook Page ID is then taken from Campaign_Config.private_page_id."
    )

def _collect_reserved_schedule_times(records: List[Tuple[int, Dict[str, Any]]]) -> set[str]:
    reserved: set[str] = set()
    for _, row in records:
        raw = str(row.get("scheduled_datetime_utc") or "").strip()
        if not raw:
            continue
        try:
            reserved.add(_format_utc(_parse_utc_datetime(raw)))
        except Exception:
            # Existing bad schedule values should be handled when that row is processed.
            continue
    return reserved


def _next_best_engagement_time_utc(
    *,
    target_tz: ZoneInfo,
    reserved_utc: set[str],
    now_utc: Optional[datetime] = None,
    min_future_minutes: int = MIN_FUTURE_MINUTES,
    slot_spacing_minutes: int = SLOT_SPACING_MINUTES,
) -> datetime:
    now_utc = now_utc or datetime.now(timezone.utc)
    earliest_utc = now_utc + timedelta(minutes=min_future_minutes)
    local_cursor = earliest_utc.astimezone(target_tz)

    for day_offset in range(0, MAX_SEARCH_DAYS):
        local_day = local_cursor.date() + timedelta(days=day_offset)
        for slot_time in _slot_times_for_date(local_day):
            candidate_local = datetime.combine(local_day, slot_time, tzinfo=target_tz)
            candidate_utc = candidate_local.astimezone(timezone.utc)
            if candidate_utc < earliest_utc:
                continue

            # Avoid assigning multiple ready posts to the exact same timestamp.
            while _format_utc(candidate_utc) in reserved_utc:
                candidate_utc += timedelta(minutes=slot_spacing_minutes)

            return candidate_utc

    raise ValueError(f"Could not calculate a valid posting slot within the next {MAX_SEARCH_DAYS} days.")


def _with_scheduled_time_if_needed(
    row: Dict[str, Any],
    *,
    target_tz: ZoneInfo,
    reserved_utc: set[str],
) -> Tuple[Dict[str, Any], Dict[str, str], Dict[str, str]]:
    """
    Return: row_for_publish, sheet_updates_before_publish, schedule_meta.

    If scheduled_datetime_utc already exists, preserve it and do not update the sheet.
    If blank, calculate a best engagement slot in the target market timezone and write
    only scheduled_datetime_utc as a needed scheduling field.
    """
    raw = str(row.get("scheduled_datetime_utc") or "").strip()
    if raw:
        scheduled_dt = _parse_utc_datetime(raw)
        normalized = _format_utc(scheduled_dt)
        row_for_publish = dict(row)
        row_for_publish["scheduled_datetime_utc"] = normalized
        reserved_utc.add(normalized)
        return row_for_publish, {}, {
            "schedule_source": "existing_sheet_value",
            "scheduled_datetime_utc": normalized,
            "scheduled_datetime_local": scheduled_dt.astimezone(target_tz).replace(microsecond=0).isoformat(),
            "target_timezone": str(target_tz),
        }

    scheduled_dt = _next_best_engagement_time_utc(target_tz=target_tz, reserved_utc=reserved_utc)
    scheduled_utc = _format_utc(scheduled_dt)
    reserved_utc.add(scheduled_utc)

    row_for_publish = dict(row)
    row_for_publish["scheduled_datetime_utc"] = scheduled_utc

    return row_for_publish, {"scheduled_datetime_utc": scheduled_utc}, {
        "schedule_source": "auto_best_engagement_slot",
        "scheduled_datetime_utc": scheduled_utc,
        "scheduled_datetime_local": scheduled_dt.astimezone(target_tz).replace(microsecond=0).isoformat(),
        "target_timezone": str(target_tz),
    }


def _updates_for_result(result: Dict[str, Any], pre_updates: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    status = str(result.get("status") or "")
    updates: Dict[str, str] = dict(pre_updates or {})

    if status in SUCCESS_PUBLISHER_STATUSES:
        updates.update({
            "post_status": SUCCESS_POST_STATUS,
            "publisher_status": status,
            "facebook_post_id": _extract_facebook_post_id(result),
            "publisher_error": "",
            "published_or_scheduled_at": str(
                result.get("scheduled_datetime_utc")
                or result.get("published_or_scheduled_at")
                or ""
            ),
        })
        return updates

    if status in ERROR_PUBLISHER_STATUSES:
        updates.update({
            "post_status": ERROR_POST_STATUS,
            "publisher_status": status,
            "publisher_error": _extract_error(result),
        })
        return updates

    updates.update({
        "post_status": ERROR_POST_STATUS,
        "publisher_status": status or "unknown_error",
        "publisher_error": _extract_error(result) or "Unknown publisher result.",
    })
    return updates


def _updates_for_exception(exc: Exception, pre_updates: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    updates: Dict[str, str] = dict(pre_updates or {})
    updates.update({
        "post_status": ERROR_POST_STATUS,
        "publisher_status": JOB_ERROR_PUBLISHER_STATUS,
        "publisher_error": str(exc),
    })
    return updates


def _assert_allowed_updates(updates: Dict[str, str]) -> None:
    invalid = sorted(set(updates) - ALLOWED_UPDATE_COLUMNS)
    if invalid:
        raise ValueError(
            "publish_ready_organic_posts_to_facebook_job attempted to update disallowed columns: "
            + ", ".join(invalid)
        )


def _update_row_fields(ws, row_idx: int, column_map: Dict[str, int], updates: Dict[str, str]) -> None:
    _assert_allowed_updates(updates)
    cells = []
    for col_name, value in updates.items():
        if col_name not in column_map:
            raise ValueError(f"Organic_Posts sheet is missing column: {col_name}")
        col_idx = column_map[col_name]
        cell = f"{_column_letter(col_idx)}{row_idx}"
        cells.append({"range": cell, "values": [[value]]})

    if cells:
        ws.batch_update(cells, value_input_option="USER_ENTERED")


def _should_process_row(row: Dict[str, Any]) -> bool:
    return str(row.get("post_status", "")).strip().lower() == READY_POST_STATUS


def _format_telegram_message(
    *,
    brand_id: str,
    page_id: str,
    posts_tab: str,
    row_number: int,
    row: Dict[str, Any],
    page_context: Dict[str, Any],
    updates: Dict[str, str],
    result: Dict[str, Any],
    schedule_meta: Dict[str, str],
) -> str:
    post_id = str(row.get("post_id") or "")
    post_status = updates.get("post_status", "")
    publisher_status = updates.get("publisher_status", result.get("status", ""))
    fb_id = updates.get("facebook_post_id", "")
    err = updates.get("publisher_error", "")
    dry_run = result.get("dry_run")

    icon = "✅" if post_status == SUCCESS_POST_STATUS else "❌"
    lines = [
        f"{icon} Facebook organic publish job",
        f"Brand: {brand_id}",
        f"Page: {page_id}",
        f"Market: {page_context.get('market', '')}",
        f"Language: {page_context.get('language', '')}",
        f"Target timezone: {schedule_meta.get('target_timezone', page_context.get('target_timezone', ''))}",
        f"Sheet: {posts_tab} / row {row_number}",
        f"Post ID: {post_id}",
        f"post_status: {post_status}",
        f"publisher_status: {publisher_status}",
    ]

    if schedule_meta:
        lines.append(f"schedule_source: {schedule_meta.get('schedule_source', '')}")
        lines.append(f"scheduled_local: {schedule_meta.get('scheduled_datetime_local', '')}")
        lines.append(f"scheduled_utc: {schedule_meta.get('scheduled_datetime_utc', '')}")
    if dry_run is not None:
        lines.append(f"dry_run: {dry_run}")
    if fb_id:
        lines.append(f"facebook_post_id: {fb_id}")
    if err:
        lines.append(f"error: {err}")

    return "\n".join(lines)


def _notify_row_result(
    notifier: TelegramNotifier,
    *,
    brand_id: str,
    page_id: str,
    posts_tab: str,
    row_number: int,
    row: Dict[str, Any],
    page_context: Dict[str, Any],
    updates: Dict[str, str],
    result: Dict[str, Any],
    schedule_meta: Dict[str, str],
) -> Dict[str, Any]:
    message = _format_telegram_message(
        brand_id=brand_id,
        page_id=page_id,
        posts_tab=posts_tab,
        row_number=row_number,
        row=row,
        page_context=page_context,
        updates=updates,
        result=result,
        schedule_meta=schedule_meta,
    )
    return notifier.send(message)


def run_publish_ready_organic_posts_to_facebook_job(
    brand_id: Optional[str] = None,
    page_id: Optional[str] = None,
    platform_id: Optional[str] = None,
    page_url: Optional[str] = None,
    max_posts: Optional[int] = None,
) -> Dict[str, Any]:
    brand_id = brand_id or os.getenv("PUBLISH_BRAND_ID", "AODAI")
    platform_id = platform_id or os.getenv("PUBLISH_PLATFORM_ID", TARGET_PLATFORM_ID)
    page_url = page_url or os.getenv("PUBLISH_PAGE_URL")

    if max_posts is None:
        raw_max_posts = os.getenv("FACEBOOK_SCHEDULE_MAX_POSTS", "").strip()
        max_posts = int(raw_max_posts) if raw_max_posts else None

    exporter = GoogleSheetsExporter()
    route = _find_route_by_brand_page_url(
        exporter,
        brand_id=brand_id,
        page_url=page_url,
        platform_id=platform_id,
    )

    brand_id = str(route.get("brand_id") or brand_id).strip()
    platform_id = str(route.get("platform_id") or platform_id).strip()
    route_page_url = _route_page_url(route)

    spreadsheet = exporter._open_spreadsheet_for_route(route)
    posts_tab = exporter._organic_tab_name(route, "posts")
    pages_tab = exporter._organic_tab_name(route, "pages")

    ws = spreadsheet.worksheet(posts_tab)
    values = ws.get_all_values()
    if not values:
        raise ValueError("Organic_Posts sheet is empty; expected a header row.")

    headers = values[0]
    column_map = _header_map(headers)
    _ensure_required_columns(column_map, REQUIRED_POST_COLUMNS, posts_tab)

    records = _rows_to_records(values, headers)
    reserved_utc = _collect_reserved_schedule_times(records)

    notifier = TelegramNotifier()
    publishers: Dict[str, FacebookPagePublisherService] = {}

    results = []
    skipped = 0

    for row_number, row in records:
        if not _should_process_row(row):
            skipped += 1
            continue

        if max_posts is not None and len(results) >= max_posts:
            break

        result: Dict[str, Any]
        updates: Dict[str, str]
        schedule_meta: Dict[str, str] = {}
        sheet_update_ok = False
        telegram_result: Dict[str, Any] = {}
        page_context: Dict[str, Any] = {}
        private_page_id = ""

        try:
            row_brand_id = str(row.get("brand_id") or brand_id).strip()
            row_platform_id = str(row.get("platform_id") or platform_id).strip()
            row_public_page_id = str(row.get("page_id") or page_id or "").strip()
            row_page_url = str(row.get("page_url") or route_page_url or "").strip()
            page_context = _load_page_context(
                spreadsheet,
                pages_tab,
                brand_id=row_brand_id,
                page_id=row_public_page_id,
                page_url=row_page_url,
                platform_id=row_platform_id,
            )
            private_page_id = str(page_context.get("private_page_id") or "").strip()
            page_access_token = str(page_context.get("token") or "").strip()
            if not private_page_id:
                raise ValueError(
                    "Campaign_Config.private_page_id is required for Facebook scheduling. "
                    f"brand_id={row_brand_id}, public_page_id={row_public_page_id}, page_url={row_page_url}"
                )
            if not page_access_token:
                raise ValueError(
                    "Campaign_Config.token is required for Facebook scheduling. "
                    f"brand_id={row_brand_id}, public_page_id={row_public_page_id}, page_url={row_page_url}"
                )
            target_tz = _resolve_target_timezone(page_context)
            publisher_key = f"{private_page_id}|{page_access_token}"
            publisher = publishers.setdefault(
                publisher_key,
                FacebookPagePublisherService(page_id=private_page_id, page_access_token=page_access_token),
            )
            row_for_publish, schedule_updates, schedule_meta = _with_scheduled_time_if_needed(
                row,
                target_tz=target_tz,
                reserved_utc=reserved_utc,
            )
            publish_payload = dict(row_for_publish)
            publish_payload["public_page_id"] = row_public_page_id
            publish_payload["page_id"] = private_page_id
            result = publisher.schedule_from_row(publish_payload)
            result["public_page_id"] = row_public_page_id
            result["private_page_id"] = private_page_id
            result.update(schedule_meta)
            updates = _updates_for_result(result, schedule_updates)
            _update_row_fields(ws, row_number, column_map, updates)
            sheet_update_ok = True
        except Exception as exc:
            result = {
                "status": JOB_ERROR_PUBLISHER_STATUS,
                "post_id": row.get("post_id"),
                "page_id": row.get("page_id"),
                "private_page_id": private_page_id,
                "error": str(exc),
            }
            updates = _updates_for_exception(exc)
            try:
                _update_row_fields(ws, row_number, column_map, updates)
                sheet_update_ok = True
            except Exception as update_exc:
                sheet_update_ok = False
                result["sheet_update_error"] = str(update_exc)

        try:
            telegram_result = _notify_row_result(
                notifier,
                brand_id=brand_id,
                page_id=str(private_page_id or row.get("page_id") or page_id or ""),
                posts_tab=posts_tab,
                row_number=row_number,
                row=row,
                page_context=page_context,
                updates=updates,
                result=result,
                schedule_meta=schedule_meta,
            )
        except Exception as notify_exc:
            telegram_result = {"status": JOB_ERROR_PUBLISHER_STATUS, "error": str(notify_exc)}

        results.append({
            "row": row_number,
            "post_id": row.get("post_id"),
            "status": result.get("status"),
            "post_status": updates.get("post_status"),
            "publisher_status": updates.get("publisher_status"),
            "dry_run": result.get("dry_run", None),
            "private_page_id": private_page_id,
            "schedule": schedule_meta,
            "sheet_update_ok": sheet_update_ok,
            "telegram": telegram_result,
            "updated_columns": list(updates.keys()),
        })

    return {
        "job": "publish_ready_organic_posts_to_facebook_job",
        "brand_id": brand_id,
        "page_id": page_id,
        "page_url": route_page_url,
        "platform_id": platform_id,
        "facebook_page_id_source": "Campaign_Config.private_page_id",
        "posts_tab": posts_tab,
        "pages_tab": pages_tab,
        "dry_run": os.getenv("FACEBOOK_PUBLISH_DRY_RUN", "false").lower() == "true",
        "ready_status": READY_POST_STATUS,
        "success_status": SUCCESS_POST_STATUS,
        "error_status": ERROR_POST_STATUS,
        "total_rows": len(records),
        "skipped": skipped,
        "processed": len(results),
        "results": results,
    }


def main() -> None:
    result = run_publish_ready_organic_posts_to_facebook_job()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
