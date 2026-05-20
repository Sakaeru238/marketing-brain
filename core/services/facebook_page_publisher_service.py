import os
import re
import unicodedata
from typing import Dict, List

from core.publishers.facebook_graph_client import FacebookGraphClient
from core.utils.facebook_publish_validator import FacebookPublishValidator
from core.publishers.facebook_publish_logger import FacebookPublishLogger


def _normalize_tag_token(value: str) -> str:
    """
    Normalize a content tag for Facebook posting while keeping the display case
    already stored in Google Sheets.

    Examples:
      #VietnameseCoffee -> VietnameseCoffee
      VietnameseCoffee  -> VietnameseCoffee
      coffee heritage   -> coffee_heritage
    """
    raw = str(value or "").strip()
    raw = raw.lstrip("#").strip()
    if not raw:
        return ""
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = re.sub(r"[\s\-]+", "_", raw)
    raw = re.sub(r"[^A-Za-z0-9_]", "", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def _split_concatenated_tag(token: str, known_tokens: List[str]) -> List[str]:
    """
    Handles duplicated pipe data like:
      mothersday|gifts|practical|coffee|familymothersday|gifts|...
    where the last tag of copy 1 and first tag of copy 2 were joined.

    Comparison is case-insensitive, while returned tags preserve the display
    casing taken from the sheet.
    """
    if not token:
        return []
    known = [t for t in known_tokens if t and t.lower() != token.lower()]
    known_by_lower = {t.lower(): t for t in known}
    token_lower = token.lower()

    for left in sorted(known, key=len, reverse=True):
        left_lower = left.lower()
        if not token_lower.startswith(left_lower):
            continue
        right_lower = token_lower[len(left_lower):]
        right = known_by_lower.get(right_lower)
        if right:
            return [left, right]
    return [token]


def _parse_content_tags(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_parts = value
    else:
        text = str(value or "").strip()
        if not text:
            return []
        raw_parts = re.split(r"[|,;\n]+", text)

    normalized = [_normalize_tag_token(part) for part in raw_parts]
    normalized = [tag for tag in normalized if tag]

    expanded = []
    for tag in normalized:
        expanded.extend(_split_concatenated_tag(tag, normalized))

    deduped = []
    seen = set()
    for tag in expanded:
        key = tag.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(tag)
    return deduped


def _append_content_hashtags(message: str, content_tags) -> str:
    message = str(message or "").strip()
    tags = _parse_content_tags(content_tags)
    if not tags:
        return message

    existing_message_lower = message.lower()
    hashtag_tokens = []
    for tag in tags:
        hashtag = f"#{tag}"
        if hashtag.lower() in existing_message_lower:
            continue
        hashtag_tokens.append(hashtag)

    if not hashtag_tokens:
        return message
    if not message:
        return " ".join(hashtag_tokens)
    return f"{message}\n\n{' '.join(hashtag_tokens)}"


class FacebookPagePublisherService:
    """
    High-level Facebook Page publisher.

    Default mode publishes real posts. Set FACEBOOK_PUBLISH_DRY_RUN=true only
    for an explicit local safety check.

    Required for real publish:
      page_id and page_access_token, normally resolved from Campaign_Config
      private_page_id and token.
    """

    def __init__(
        self,
        page_id: str = None,
        page_access_token: str = None,
        graph_client: FacebookGraphClient = None,
        validator: FacebookPublishValidator = None,
        logger: FacebookPublishLogger = None,
        dry_run: bool = None,
    ):
        self.graph_client = graph_client or FacebookGraphClient(
            page_id=page_id,
            page_access_token=page_access_token,
        )
        self.validator = validator or FacebookPublishValidator()
        self.logger = logger or FacebookPublishLogger()

        if dry_run is None:
            dry_run = os.getenv("FACEBOOK_PUBLISH_DRY_RUN", "false").lower() == "true"
        self.dry_run = dry_run

    def schedule_from_row(self, row: Dict) -> Dict:
        valid, errors = self.validator.validate(row)

        post_id = row.get("post_id", "")
        page_id = row.get("page_id", "")
        public_page_id = row.get("public_page_id", "")
        image_url = str(row.get("image_url", "") or "").strip()
        message = str(row.get("post_text", "") or "").strip()
        message = _append_content_hashtags(message, row.get("content_tags", ""))
        scheduled_utc = str(row.get("scheduled_datetime_utc", "") or "").strip()

        if not valid:
            result = {
                "status": "validation_error",
                "post_id": post_id,
                "page_id": page_id,
                "public_page_id": public_page_id,
                "errors": errors,
            }
            self.logger.log({"action": "validate", **result})
            return result

        scheduled_ts = self.validator.to_unix_timestamp(scheduled_utc)

        if self.dry_run:
            endpoint = "photos" if image_url else "feed"
            result = {
                "status": "dry_run",
                "dry_run": True,
                "post_id": post_id,
                "page_id": page_id,
                "public_page_id": public_page_id,
                "endpoint": endpoint,
                "scheduled_datetime_utc": scheduled_utc,
                "image_url_present": bool(image_url),
                "content_hashtags": _parse_content_tags(row.get("content_tags", "")),
                "facebook_response": {
                    "id": f"dryrun_{post_id}"
                },
            }
            self.logger.log({"action": "schedule_dry_run", **result})
            return result

        try:
            if image_url:
                fb_response = self.graph_client.schedule_photo_post(
                    caption=message,
                    image_url=image_url,
                    scheduled_publish_time=scheduled_ts,
                )
            else:
                fb_response = self.graph_client.schedule_feed_post(
                    message=message,
                    scheduled_publish_time=scheduled_ts,
                )

            result = {
                "status": "scheduled",
                "dry_run": False,
                "post_id": post_id,
                "page_id": page_id,
                "public_page_id": public_page_id,
                "scheduled_datetime_utc": scheduled_utc,
                "image_url_present": bool(image_url),
                "content_hashtags": _parse_content_tags(row.get("content_tags", "")),
                "facebook_response": fb_response,
            }
            self.logger.log({"action": "schedule_real", **result})
            return result

        except Exception as e:
            result = {
                "status": "error",
                "post_id": post_id,
                "page_id": page_id,
                "public_page_id": public_page_id,
                "error": str(e),
            }
            self.logger.log({"action": "schedule_error", **result})
            return result
