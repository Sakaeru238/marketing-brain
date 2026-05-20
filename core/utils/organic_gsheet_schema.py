import json
from pathlib import Path
from typing import Any, Dict, List

from core.config.paths import GLOBAL_CONFIG_DIR


def load_organic_gsheet_schema() -> Dict[str, Any]:
    schema_file = GLOBAL_CONFIG_DIR / "gsheet_schema.json"
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    return ((schema.get("modules") or {}).get("organic") or {})


def organic_tab_name(key: str) -> str:
    tabs = (load_organic_gsheet_schema().get("tabs") or {})
    value = str(tabs.get(key) or "").strip()
    if not value:
        raise ValueError(f"Organic Google Sheet tab is not configured for key: {key}")
    return value


def organic_post_default_values() -> Dict[str, Any]:
    return dict(((load_organic_gsheet_schema().get("posts") or {}).get("default_values") or {}))


def organic_post_status_values() -> Dict[str, Any]:
    return dict(((load_organic_gsheet_schema().get("posts") or {}).get("status_values") or {}))


def organic_publish_job_config() -> Dict[str, Any]:
    return dict(load_organic_gsheet_schema().get("publish_ready_to_facebook_job") or {})


def organic_status_list(key: str) -> List[str]:
    values = organic_post_status_values().get(key) or []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    value = str(values or "").strip()
    return [value] if value else []
