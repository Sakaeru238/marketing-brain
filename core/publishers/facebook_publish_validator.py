from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from urllib.parse import urlparse


class FacebookPublishValidator:
    """
    Validates a Google Sheet row before scheduling it to Facebook.

    Current scheduling flow:
      - Organic_Posts.post_status == "ready" means the row is ready for the job.
      - After a successful schedule/publish, the job updates post_status -> "posted".
      - If an error happens, the job updates post_status -> "error".

    "approved" is still accepted for backwards compatibility with older sheets.
    """

    def __init__(self, min_future_minutes: int = 15):
        self.min_future_minutes = min_future_minutes
        self.allowed_post_statuses = {"ready", "approved"}

    def validate(self, row: Dict) -> Tuple[bool, List[str]]:
        errors = []

        post_status = str(row.get("post_status", "")).strip().lower()
        publisher_status = str(row.get("publisher_status", "")).strip().lower()
        platform_id = str(row.get("platform_id", "")).strip().lower()

        if platform_id and platform_id != "facebook":
            errors.append(f"platform_id must be facebook, got: {platform_id}")

        if post_status not in self.allowed_post_statuses:
            errors.append(
                "post_status must be ready. "
                "approved is accepted only for backward compatibility."
            )

        if publisher_status in ["scheduled", "published", "scheduled_dry_run"]:
            errors.append(f"publisher_status already processed: {publisher_status}")

        if publisher_status == "error":
            errors.append("publisher_status is error. Clear it manually after review before retrying.")

        if not str(row.get("post_text", "")).strip():
            errors.append("post_text is required.")

        scheduled = str(row.get("scheduled_datetime_utc", "")).strip()
        if not scheduled:
            errors.append("scheduled_datetime_utc is required.")
        else:
            try:
                dt = self.parse_utc_datetime(scheduled)
                min_dt = datetime.now(timezone.utc) + timedelta(minutes=self.min_future_minutes)
                if dt < min_dt:
                    errors.append(
                        f"scheduled_datetime_utc must be at least {self.min_future_minutes} minutes in the future."
                    )
            except Exception as e:
                errors.append(f"scheduled_datetime_utc is invalid: {e}")

        image_url = str(row.get("image_url", "")).strip()
        if image_url:
            errors.extend(self.validate_image_url(image_url))

        return len(errors) == 0, errors

    def parse_utc_datetime(self, value: str) -> datetime:
        value = value.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def to_unix_timestamp(self, value: str) -> int:
        return int(self.parse_utc_datetime(value).timestamp())

    def validate_image_url(self, image_url: str) -> List[str]:
        errors = []
        parsed = urlparse(image_url)

        if parsed.scheme != "https":
            errors.append("image_url must start with https://")

        if parsed.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
            errors.append("image_url must be public, not localhost.")

        if not parsed.netloc:
            errors.append("image_url is not a valid URL.")

        return errors
