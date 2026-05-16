from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


class BehavioralScheduleEngine:
    FALLBACK_WINDOWS = {
        "morning_coffee": ("07:30", "09:00"),
        "lunch_scroll": ("11:45", "12:45"),
        "evening_scroll": ("19:30", "20:45"),
    }

    def choose_window(self, post, historical_learning=None):
        historical_learning = historical_learning or {}
        archetype = (post.get("content_archetype") or "").lower()
        trigger = (post.get("interaction_trigger_type") or "").lower()
        desired_action = (post.get("desired_action") or "").lower()
        pillar = (post.get("content_pillar") or "").lower()
        target_human = (post.get("target_human") or "").lower()

        learned = historical_learning.get("best_windows_by_archetype", {})
        if archetype in learned and learned[archetype].get("confidence") in ["medium", "high"]:
            return learned[archetype]["window"], "historical page learning", learned[archetype]["confidence"]

        if "coffee" in pillar or "morning" in pillar or "mom" in target_human:
            return "morning_coffee", "Audience likely reacts during morning routine context.", "low"
        if archetype == "educational" or desired_action == "save":
            return "lunch_scroll", "Educational/save-oriented content tends to fit midday scrolling.", "low"
        if archetype == "humor" or trigger in ["humor_tagging", "debate", "controversial_light", "hot_take"]:
            return "evening_scroll", "Humor/debate content often fits evening leisure behavior.", "low"
        return "evening_scroll", "Fallback to evening engagement window for broader social reaction.", "none"

    def assign(self, post, start_date_local=None, target_timezone="America/New_York", historical_learning=None):
        tz = ZoneInfo(target_timezone)
        base_date = datetime.fromisoformat(start_date_local).date() if start_date_local else datetime.now(tz).date() + timedelta(days=1)
        window, reason, confidence = self.choose_window(post, historical_learning)
        start_time, _ = self.FALLBACK_WINDOWS.get(window, self.FALLBACK_WINDOWS["evening_scroll"])
        hour, minute = [int(x) for x in start_time.split(":")]
        local_dt = datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)
        post["recommended_posting_window"] = window
        post["behavioral_reason"] = post.get("behavioral_reason") or reason
        post["historical_confidence"] = post.get("historical_confidence") or confidence
        post["scheduled_date_local"] = local_dt.date().isoformat()
        post["scheduled_time_local"] = local_dt.strftime("%H:%M")
        post["scheduled_datetime_local"] = local_dt.strftime("%Y-%m-%dT%H:%M:%S")
        post["scheduled_datetime_utc"] = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        post["schedule_reason"] = post.get("schedule_reason") or reason
        return post
