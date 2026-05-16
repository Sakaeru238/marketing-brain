from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


class PostScheduleEngine:
    """Assigns schedule fields using target audience timezone, not admin timezone."""

    DEFAULT_WINDOWS = {
        "morning_coffee": ("07:30", "09:00"),
        "lunch_scroll": ("11:45", "12:45"),
        "evening_scroll": ("19:30", "20:45"),
    }

    ROLE_WINDOW_MAP = {
        "routine_post": "morning_coffee",
        "soft_product_mention": "morning_coffee",
        "relatable_observation": "morning_coffee",
        "educational_post": "lunch_scroll",
        "myth_busting": "lunch_scroll",
        "community_question": "evening_scroll",
        "conversation_starter": "evening_scroll",
        "soft_story": "evening_scroll",
        "brand_belief": "evening_scroll",
    }

    def choose_window(self, content_role: str, content_pillar: str = "") -> str:
        content_role = (content_role or "").strip()
        content_pillar = (content_pillar or "").lower()
        if "coffee" in content_pillar or "morning" in content_pillar:
            return "morning_coffee"
        return self.ROLE_WINDOW_MAP.get(content_role, "evening_scroll")

    def assign_schedule(self, posts, start_date_local=None, target_timezone="America/New_York", target_market="US"):
        tz = ZoneInfo(target_timezone)
        base_date = datetime.fromisoformat(start_date_local).date() if start_date_local else datetime.now(tz).date() + timedelta(days=1)

        scheduled = []
        for idx, post in enumerate(posts):
            window = post.get("posting_window") or self.choose_window(post.get("content_role"), post.get("content_pillar"))
            local_date = base_date + timedelta(days=idx)
            start_time, _ = self.DEFAULT_WINDOWS.get(window, self.DEFAULT_WINDOWS["evening_scroll"])
            hour, minute = [int(x) for x in start_time.split(":")]

            local_dt = datetime(local_date.year, local_date.month, local_date.day, hour, minute, 0, tzinfo=tz)
            utc_dt = local_dt.astimezone(timezone.utc)

            post["target_market"] = post.get("target_market") or target_market
            post["target_timezone"] = post.get("target_timezone") or target_timezone
            post["posting_window"] = window
            post["schedule_basis"] = post.get("schedule_basis") or "target_audience_timezone"
            post["scheduled_date_local"] = post.get("scheduled_date_local") or local_dt.date().isoformat()
            post["scheduled_time_local"] = post.get("scheduled_time_local") or local_dt.strftime("%H:%M")
            post["scheduled_datetime_local"] = post.get("scheduled_datetime_local") or local_dt.strftime("%Y-%m-%dT%H:%M:%S")
            post["scheduled_datetime_utc"] = post.get("scheduled_datetime_utc") or utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            post["schedule_reason"] = post.get("schedule_reason") or self._reason(window, target_timezone)
            scheduled.append(post)

        return scheduled

    def _reason(self, window, target_timezone):
        if window == "morning_coffee":
            return f"Scheduled for audience morning coffee behavior in {target_timezone}, not Vietnam/admin timezone."
        if window == "lunch_scroll":
            return f"Scheduled for audience lunch scroll behavior in {target_timezone}, not Vietnam/admin timezone."
        return f"Scheduled for audience evening engagement behavior in {target_timezone}, not Vietnam/admin timezone."
