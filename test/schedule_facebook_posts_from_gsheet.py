from dotenv import load_dotenv
load_dotenv()
import json
import os
from typing import Dict, List

from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.publishers.facebook_page_publisher import FacebookPagePublisher


REQUIRED_COLUMNS = [
    "post_id",
    "brand_id",
    "page_id",
    "platform_id",
    "post_text",
    "image_url",
    "post_status",
    "publisher_status",
    "facebook_post_id",
    "publisher_error",
    "scheduled_datetime_utc",
    "published_or_scheduled_at",
]


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


def _ensure_required_columns(column_map: Dict[str, int]):
    missing = [col for col in REQUIRED_COLUMNS if col not in column_map]
    if missing:
        raise ValueError(
            "Organic_Posts sheet is missing required columns: "
            + ", ".join(missing)
        )


def _update_row_status(ws, row_idx: int, column_map: Dict[str, int], result: Dict):
    status = result.get("status")
    fb_response = result.get("facebook_response", {}) or {}
    facebook_post_id = fb_response.get("id") or fb_response.get("post_id") or ""
    error = result.get("error") or "; ".join(result.get("errors", []) or "")
    scheduled_at = "" if status in ["validation_error", "error"] else result.get("scheduled_datetime_utc", "")

    updates = {
        "publisher_status": status,
        "facebook_post_id": facebook_post_id,
        "publisher_error": error,
        "published_or_scheduled_at": scheduled_at,
    }

    for col_name, value in updates.items():
        col_idx = column_map[col_name]
        cell = f"{_column_letter(col_idx)}{row_idx}"
        ws.update(cell, [[value]])


def main():
    brand_id = os.getenv("PUBLISH_BRAND_ID", "AODAI")
    page_id = os.getenv("PUBLISH_PAGE_ID", "AODAI_FB_US")
    platform_id = os.getenv("PUBLISH_PLATFORM_ID", "facebook")

    exporter = GoogleSheetsExporter()
    route = exporter._find_route(
        brand_id=brand_id,
        page_id=page_id,
        platform_id=platform_id,
        
    )

    meta_page_id = route.get("page_id")
    
    spreadsheet = exporter._open_spreadsheet_for_route(route)
    posts_tab = exporter._tab_name(route, "posts", "Organic_Posts")
    ws = spreadsheet.worksheet(posts_tab)

    headers = ws.row_values(1)
    column_map = _header_map(headers)
    _ensure_required_columns(column_map)

    records = ws.get_all_records()
    publisher = FacebookPagePublisher(page_id = meta_page_id)

    results = []
    for row_number, row in enumerate(records, start=2):
        row_post_status = str(row.get("post_status", "")).strip().lower()
        row_publisher_status = str(row.get("publisher_status", "")).strip().lower()

        if row_post_status != "approved":
            continue

        if row_publisher_status in ["scheduled", "published", "scheduled_dry_run"]:
            continue

        result = publisher.schedule_from_row(row)
        _update_row_status(ws, row_number, column_map, result)
        results.append(
            {
                "row": row_number,
                "post_id": row.get("post_id"),
                "status": result.get("status"),
                "dry_run": result.get("dry_run", None),
            }
        )

    print(
        json.dumps(
            {
                "brand_id": brand_id,
                "page_id": page_id,
                "platform_id": platform_id,
                "posts_tab": posts_tab,
                "processed": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
