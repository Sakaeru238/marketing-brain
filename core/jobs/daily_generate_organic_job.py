from dotenv import load_dotenv
load_dotenv()

import json
import traceback
from typing import Dict, List

from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.notifications.telegram_notifier import TelegramNotifier
from core.services.organic_generation_service import OrganicGenerationService


def is_active(value) -> bool:
    return str(value or "").strip().lower() == "active"


def _records_safe(ws) -> List[Dict]:
    values = ws.get_all_values()
    if not values:
        return []
    headers = [str(header or "").strip() for header in values[0]]
    rows = []
    for row_values in values[1:]:
        record = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            record[header] = row_values[idx] if idx < len(row_values) else ""
        if any(str(value or "").strip() for value in record.values()):
            rows.append(record)
    return rows


def load_active_page_tasks():
    exporter = GoogleSheetsExporter()
    tasks = []

    for route in exporter.routes:
        if not is_active(route.get("status", "active")):
            continue

        spreadsheet = exporter._open_spreadsheet_for_route(route)
        pages_tab = exporter._tab_name(route, "pages", "Page_Channel_Library")
        ws = spreadsheet.worksheet(pages_tab)
        rows = _records_safe(ws)

        for row in rows:
            if not is_active(row.get("status")):
                continue

            brand_id = str(row.get("brand_id") or "").strip()
            page_id = str(row.get("page_id") or "").strip()
            platform_id = str(row.get("platform_id") or "").strip()
            campaign_id = str(row.get("campaign_id") or "").strip()
            niche_id = str(row.get("niche_id") or "").strip()

            if not brand_id or not page_id or not platform_id or not campaign_id:
                continue

            tasks.append({
                "brand_id": brand_id,
                "page_id": page_id,
                "platform_id": platform_id,
                "campaign_id": campaign_id,
                "niche_id": niche_id,
                "page_name": row.get("page_name", ""),
                "notes": row.get("notes", ""),
            })

    return tasks


def main():
    notifier = TelegramNotifier()
    service = OrganicGenerationService()

    tasks = load_active_page_tasks()
    if not tasks:
        message = "⚠️ No active organic tasks found in Page_Channel_Library."
        notifier.send(message)
        print(json.dumps({"status": "no_tasks", "tasks": []}, ensure_ascii=False, indent=2))
        return

    results = []
    notifier.send(f"🚀 Daily organic generation started\nTasks found: {len(tasks)}")

    for task in tasks:
        try:
            result = service.run(
                brand_id=task["brand_id"],
                page_id=task["page_id"],
                platform_id=task["platform_id"],
            )
            results.append({
                "brand_id": task["brand_id"],
                "page_id": task["page_id"],
                "campaign_id": task.get("campaign_id"),
                "platform_id": task["platform_id"],
                "status": "success",
                "rows_appended": result.get("export_result", {}).get("rows_appended"),
                "kpi_status": result.get("campaign_kpi_context", {}).get("kpi_status"),
                "content_intensity": result.get("campaign_kpi_context", {}).get("content_intensity"),
                "organic_strategy_mode": result.get("organic_strategy_mode"),
                "organic_strategy_review_decision": result.get("organic_strategy_review_decision", {}),
                "organic_strategy_output_file": result.get("organic_strategy_output_file"),
                "organic_output_file": result.get("output_file"),
            })
        except Exception as exc:
            print(traceback.format_exc())
            results.append({
                "brand_id": task["brand_id"],
                "page_id": task["page_id"],
                "campaign_id": task.get("campaign_id"),
                "platform_id": task["platform_id"],
                "status": "error",
                "error": str(exc),
            })
            notifier.send(
                "❌ Organic generation failed\n"
                f"Brand: {task['brand_id']}\n"
                f"Page: {task['page_id']}\n"
                f"Campaign: {task.get('campaign_id', '')}\n"
                f"Platform: {task['platform_id']}\n"
                f"Error: {str(exc)}"
            )

    success_count = len([result for result in results if result["status"] == "success"])
    error_count = len([result for result in results if result["status"] == "error"])

    notifier.send(
        "✅ Daily organic generation finished\n"
        f"Success: {success_count}\n"
        f"Errors: {error_count}"
    )

    print(json.dumps({
        "status": "finished",
        "tasks_found": len(tasks),
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
