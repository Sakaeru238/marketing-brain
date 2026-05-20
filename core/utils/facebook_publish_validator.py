from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from core.utils.organic_gsheet_schema import (
    organic_post_status_values,
    organic_publish_job_config,
    organic_status_list,
)


class FacebookPublishValidator:
    """
    Validates a Google Sheet row before scheduling it to Facebook.

    Current scheduling flow:
      - Organic_Posts.post_status == "ready" means the row is ready for the job.
      - After a successful schedule/publish, the job updates post_status -> "posted".
      - If an error happens, the job updates post_status -> "error".

    """

    def __init__(self, min_future_minutes: int = None):
        publish_config = organic_publish_job_config()
        schedule_policy = publish_config.get("schedule_policy") or {}
        validation_policy = publish_config.get("validation_policy") or {}
        self.target_platform_id = str(publish_config["target_platform_id"]).strip().lower()
        self.platform_field = str(validation_policy["platform_field"])
        self.post_status_field = str(validation_policy["post_status_field"])
        self.publisher_status_field = str(validation_policy["publisher_status_field"])
        self.required_text_field = str(validation_policy["required_text_field"])
        self.scheduled_datetime_field = str(validation_policy["scheduled_datetime_field"])
        self.image_url_field = str(validation_policy["image_url_field"])
        self.image_url_required_scheme = str(validation_policy["image_url_required_scheme"])
        self.blocked_image_url_hosts = {
            str(host).strip()
            for host in validation_policy["blocked_image_url_hosts"]
            if str(host).strip()
        }
        self.min_future_minutes = (
            int(min_future_minutes)
            if min_future_minutes is not None
            else int(schedule_policy["min_future_minutes"])
        )
        status_values = organic_post_status_values()
        self.ready_post_status = str(status_values["ready_post_status"])
        self.allowed_post_statuses = {self.ready_post_status}
        self.blocked_publisher_statuses = set(organic_status_list("blocked_publisher_statuses"))

    def validate(self, row: Dict) -> Tuple[bool, List[str]]:
        errors = []

        post_status = str(row.get(self.post_status_field, "")).strip().lower()
        publisher_status = str(row.get(self.publisher_status_field, "")).strip().lower()
        platform_id = str(row.get(self.platform_field, "")).strip().lower()

        if platform_id and platform_id != self.target_platform_id:
            errors.append(f"{self.platform_field} must be {self.target_platform_id}, got: {platform_id}")

        if post_status not in self.allowed_post_statuses:
            errors.append(
                f"post_status must be {self.ready_post_status}."
            )

        if publisher_status in self.blocked_publisher_statuses:
            errors.append(f"publisher_status already processed: {publisher_status}")

        if publisher_status in set(organic_status_list("error_publisher_statuses")):
            errors.append("publisher_status is error. Clear it manually after review before retrying.")

        if not str(row.get(self.required_text_field, "")).strip():
            errors.append(f"{self.required_text_field} is required.")

        scheduled = str(row.get(self.scheduled_datetime_field, "")).strip()
        if not scheduled:
            errors.append(f"{self.scheduled_datetime_field} is required.")
        else:
            try:
                dt = self.parse_utc_datetime(scheduled)
                min_dt = datetime.now(timezone.utc) + timedelta(minutes=self.min_future_minutes)
                if dt < min_dt:
                    errors.append(
                        f"{self.scheduled_datetime_field} must be at least {self.min_future_minutes} minutes in the future."
                    )
            except Exception as e:
                errors.append(f"{self.scheduled_datetime_field} is invalid: {e}")

        image_url = str(row.get(self.image_url_field, "")).strip()
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

        if parsed.scheme != self.image_url_required_scheme:
            errors.append(f"{self.image_url_field} must start with {self.image_url_required_scheme}://")

        if parsed.hostname in self.blocked_image_url_hosts:
            errors.append(f"{self.image_url_field} must be public, not localhost.")

        if not parsed.netloc:
            errors.append(f"{self.image_url_field} is not a valid URL.")

        return errors
