from datetime import datetime, date


class CampaignKPICalculator:
    DATE_FORMAT = "%Y-%m-%d"

    def _parse_date(self, value):
        if not value:
            return None
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value).strip(), self.DATE_FORMAT).date()

    def _to_int(self, value, default=0):
        try:
            if value in [None, ""]:
                return default
            return int(float(value))
        except Exception:
            return default

    def calculate(self, page_row, today=None):
        today = today or date.today()

        start_day = self._parse_date(page_row.get("start_day"))
        end_day = self._parse_date(page_row.get("end_day"))

        duration = self._to_int(page_row.get("duration"))
        if duration <= 0 and start_day and end_day:
            duration = max((end_day - start_day).days + 1, 1)

        current_followers = self._to_int(page_row.get("current_followers"))
        current_likes = self._to_int(page_row.get("current_likes"))
        target_followers = self._to_int(page_row.get("target_followers"))
        target_likes = self._to_int(page_row.get("target_likes"))

        follower_gap = max(target_followers - current_followers, 0)
        like_gap = max(target_likes - current_likes, 0)

        days_elapsed = max((today - start_day).days + 1, 0) if start_day else 0
        if end_day:
            days_remaining = max((end_day - today).days + 1, 0)
        else:
            days_remaining = max(duration - days_elapsed, 0) if duration else 0

        campaign_progress_percent = min(round((days_elapsed / duration) * 100, 2), 100) if duration else 0
        required_followers_per_day = round(follower_gap / days_remaining, 2) if days_remaining else follower_gap
        required_likes_per_day = round(like_gap / days_remaining, 2) if days_remaining else like_gap

        follower_progress_percent = round((current_followers / target_followers) * 100, 2) if target_followers else 0
        like_progress_percent = round((current_likes / target_likes) * 100, 2) if target_likes else 0

        if days_remaining <= 0:
            kpi_status = "ended"
        elif follower_progress_percent + 10 < campaign_progress_percent:
            kpi_status = "behind"
        elif follower_progress_percent >= campaign_progress_percent:
            kpi_status = "on_track"
        else:
            kpi_status = "slightly_behind"

        if kpi_status == "behind":
            content_intensity = "aggressive"
            recommended_archetype_shift = [
                "increase humor",
                "increase relatable/shareable emotional",
                "increase light debate/hot_take",
                "reduce low-reaction product-heavy posts",
            ]
        elif kpi_status == "slightly_behind":
            content_intensity = "moderate_high"
            recommended_archetype_shift = [
                "increase relatable content",
                "increase conversation starters",
                "keep product mention soft",
            ]
        else:
            content_intensity = "normal"
            recommended_archetype_shift = [
                "maintain balanced archetype mix",
                "continue testing interaction triggers",
            ]

        return {
            "start_day": start_day.isoformat() if start_day else "",
            "end_day": end_day.isoformat() if end_day else "",
            "duration": duration,
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "campaign_progress_percent": campaign_progress_percent,
            "current_followers": current_followers,
            "current_likes": current_likes,
            "target_followers": target_followers,
            "target_likes": target_likes,
            "follower_gap": follower_gap,
            "like_gap": like_gap,
            "follower_progress_percent": follower_progress_percent,
            "like_progress_percent": like_progress_percent,
            "required_followers_per_day": required_followers_per_day,
            "required_likes_per_day": required_likes_per_day,
            "kpi_status": kpi_status,
            "content_intensity": content_intensity,
            "recommended_archetype_shift": recommended_archetype_shift,
        }
