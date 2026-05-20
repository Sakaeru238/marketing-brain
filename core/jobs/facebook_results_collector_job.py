from datetime import datetime, timezone

from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.notifications.telegram_notifier import TelegramNotifier
from core.publishers.facebook_graph_client import FacebookGraphClient


class FacebookResultsCollectorJob:
    FIELDS = "id,message,created_time,permalink_url,shares,comments.summary(true),reactions.summary(true)"

    def __init__(self):
        self.exporter = GoogleSheetsExporter()
        self.client = FacebookGraphClient()
        self.notifier = TelegramNotifier()

    def run(self, brand_id="AODAI", page_id="AODAI_FB_US", platform_id="facebook"):
        route = self.exporter._find_route(brand_id, page_id, platform_id)
        spreadsheet = self.exporter._open_spreadsheet_for_route(route)
        posts_tab = self.exporter._organic_tab_name(route, "posts")
        ws = spreadsheet.worksheet(posts_tab)
        rows = ws.get_all_records()

        collected = []
        for row in rows:
            fb_id = str(row.get("facebook_post_id", "")).strip()
            if not fb_id or fb_id.startswith("dryrun_"):
                continue
            try:
                data = self.client.get_object(fb_id, fields=self.FIELDS)
                collected.append(
                    {
                        "campaign_id": row.get("campaign_id", ""),
                        "post_id": row.get("post_id"),
                        "facebook_post_id": fb_id,
                        "post_url": data.get("permalink_url", ""),
                        "published_date": data.get("created_time", ""),
                        "likes": (
                            (data.get("reactions") or {}).get("summary") or {}
                        ).get("total_count", 0),
                        "comments": (
                            (data.get("comments") or {}).get("summary") or {}
                        ).get("total_count", 0),
                        "shares": (data.get("shares") or {}).get("count", 0),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            except Exception as e:
                collected.append(
                    {
                        "post_id": row.get("post_id"),
                        "facebook_post_id": fb_id,
                        "error": str(e),
                    }
                )

        results_tab = self.exporter._organic_tab_name(route, "results")
        results_ws = spreadsheet.worksheet(results_tab)

        records_to_write = [
            r for r in collected
            if not r.get("error")
        ]

        rows_written = self.exporter._append_records_by_headers(
            worksheet=results_ws,
            records=records_to_write,
            required_headers=self.exporter.ORGANIC_RESULTS_HEADERS,
        )
        
        self.notifier.send(
            f"📊 Facebook results collected\n"
            f"Brand: {brand_id}\n"
            f"Page: {page_id}\n"
            f"Posts checked: {len(collected)}\n"
            f"Rows written: {rows_written}"
        )
        return collected
