from datetime import datetime, timezone

from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.notifications.telegram_notifier import TelegramNotifier


class RollingContentQueueJob:
    def __init__(self, min_future_posts=3):
        self.min_future_posts = min_future_posts
        self.exporter = GoogleSheetsExporter()
        self.notifier = TelegramNotifier()

    def run(self, brand_id="AODAI", page_id="AODAI_FB_US", platform_id="facebook"):
        route = self.exporter._find_route(brand_id, page_id, platform_id)
        spreadsheet = self.exporter._open_spreadsheet_for_route(route)
        tab = self.exporter._organic_tab_name(route, "posts")
        ws = spreadsheet.worksheet(tab)
        rows = ws.get_all_records()
        now = datetime.now(timezone.utc)
        future = []
        for row in rows:
            dt_raw = str(row.get("scheduled_datetime_utc", "")).strip()
            if not dt_raw:
                continue
            try:
                dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
                if dt > now and str(row.get("publisher_status", "")).lower() not in ["published", "error"]:
                    future.append(row)
            except Exception:
                pass
        if len(future) < self.min_future_posts:
            self.notifier.send(f"⚠️ Organic content queue low\nBrand: {brand_id}\nPage: {page_id}\nFuture posts: {len(future)}\nAction: generate more future posts.")
            return {"queue_status": "low", "future_posts": len(future), "should_generate": True}
        return {"queue_status": "healthy", "future_posts": len(future), "should_generate": False}
