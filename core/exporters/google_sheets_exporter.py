import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import gspread

from core.services.brand_registry_service import BrandRegistryService


class GoogleSheetsExporter:
    """
    Exports Organic Engine outputs to brand-specific Google Sheets.

    Routing prefers per-brand config files under config/brands/{brand_id}/gsheet_settings.json.
    Legacy fallback remains config/google_sheet_routing.json.
    Mapping: brand_id + page_id -> google_sheet_url.

    Final V10 notes:
    - This remains the only Google Sheets exporter.
    - No duplicate google_sheets_organic_appender.py is needed.
    - Organic_Posts does NOT store post_url / published_date.
    - Organic_Results stores post_url / published_date after Facebook collector runs.
    - Organic_Posts appends rows, it does not overwrite existing rows.
    """

    ORGANIC_POSTS_HEADERS = [
        "campaign_id",
        "organic_run_id",
        "post_id",
        "created_at",
        "brand_id",
        "niche_id",
        "page_id",
        "platform_id",
        "page_url",
        "content_archetype",
        "interaction_trigger_type",
        "target_human",
        "current_emotional_state",
        "core_problem",
        "core_solution",
        "primary_takeaway",
        "desired_post_outcome",
        "desired_action",
        "awareness_stage",
        "planned_publish_day",
        "current_followers_snapshot",
        "current_likes_snapshot",
        "post_format",
        "content_role",
        "content_pillar",
        "angle_used",
        "hook_type",
        "product_mention_level",
        "hook",
        "post_text",
        "engagement_prompt",
        "chatgpt_image_prompt",
        "content_tags",
        "seo_keywords_used",
        "brand_keywords_used",
        "trend_keywords_used",
        "platform_native_keywords",
        "expected_primary_reaction",
        "why_people_would_like",
        "why_people_would_comment",
        "why_people_would_share",
        "possible_light_disagreement",
        "image_intent",
        "product_reference_required",
        "product_reference_note",
        "image_url",
        "recommended_posting_window",
        "behavioral_reason",
        "historical_confidence",
        "scheduled_datetime_utc",
        "campaign_kpi_status",
        "campaign_content_intensity",
        "why_this_post_fits_kpi",
        "post_status",
        "publisher_status",
        "facebook_post_id",
        "publisher_error",
        "published_or_scheduled_at",
        "notes_user",
    ]

    ORGANIC_RESULTS_HEADERS = [
        "campaign_id",
        "organic_run_id",
        "date",
        "post_id",
        "brand_id",
        "niche_id",
        "page_id",
        "platform_id",
        "facebook_post_id",
        "published_date",
        "post_url",
        "content_archetype",
        "interaction_trigger_type",
        "target_human",
        "core_problem",
        "desired_post_outcome",
        "desired_action",
        "content_tags",
        "seo_keywords_used",
        "recommended_posting_window",
        "likes",
        "comments",
        "shares",
        "saves",
        "reach",
        "impressions",
        "clicks",
        "follows",
        "engagement_rate",
        "result_notes_user",
        "ai_result_summary",
        "ai_learning",
        "ai_next_action",
        "collected_at",
    ]

    DAILY_LEARNING_HEADERS = [
        "campaign_id",
        "learning_id",
        "date",
        "brand_id",
        "niche_id",
        "page_id",
        "platform_id",
        "organic_run_id",
        "growth_goal",
        "today_content_goal",
        "posts_reviewed",
        "best_post_id",
        "worst_post_id",
        "winning_content_roles_ai",
        "weak_content_roles_ai",
        "winning_pillars_ai",
        "weak_pillars_ai",
        "winning_hooks_ai",
        "weak_hooks_ai",
        "audience_signal_ai",
        "content_improvement_ai",
        "keep_strategy_ai",
        "strategy_review_needed_ai",
        "next_day_content_goal_ai",
        "next_day_content_roles_ai",
        "next_day_content_pillars_ai",
        "next_day_post_format_mix_ai",
        "next_day_product_mention_level_ai",
        "next_day_tone_ai",
        "next_day_notes_ai",
    ]

    PAGE_CHANNEL_HEADERS = [
        "campaign_id",
        "page_id",
        "brand_id",
        "niche_id",
        "platform_id",
        "page_name",
        "page_url",
        "meta_page_id",
        "market",
        "language",
        "target_timezone",
        "page_stage",
        "current_followers",
        "current_likes",
        "target_followers",
        "target_likes",
        "primary_growth_metric",
        "growth_goal",
        "start_day",
        "end_day",
        "duration",
        "default_content_goal",
        "default_tone",
        "default_product_mention_level",
        "posting_frequency_target",
        "status",
        "notes",
    ]

    BRAND_CONFIG_HEADERS = [
        "brand_id",
        "brand_name",
        "niche_id",
        "brand_context_folder",
        "brand_intake_file",
        "default_language",
        "default_market",
        "notes",
    ]

    def __init__(
        self,
        routing_file: str = "config/google_sheet_routing.json",
        oauth_client_file: Optional[str] = None,
        oauth_token_file: Optional[str] = None,
    ):
        self.routing_file = Path(routing_file)
        self.oauth_client_file = (
            oauth_client_file
            or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
            or "secrets/google_oauth_client_secret.json"
        )
        self.oauth_token_file = (
            oauth_token_file
            or os.getenv("GOOGLE_OAUTH_TOKEN_FILE")
            or "secrets/google_oauth_token.json"
        )
        self.routes = self._load_routes()
        self.client = self._authorize()

    def _load_routes(self) -> List[Dict]:
        """Load Google Sheet routes.

        Preferred source: per-brand config folders under config/brands/{brand_id}/
        Legacy fallback: config/google_sheet_routing.json

        The fallback is intentionally kept so the currently working organic jobs
        remain compatible during the multi-brand migration.
        """
        brand_routes = self._load_routes_from_brand_configs()
        if brand_routes:
            return brand_routes

        if not self.routing_file.exists():
            raise FileNotFoundError(
                f"Google Sheet routing file not found: {self.routing_file}"
            )
        data = json.loads(self.routing_file.read_text(encoding="utf-8"))
        routes = data.get("routes", [])
        if not routes:
            raise ValueError(f"No routes found in {self.routing_file}")
        return routes

    def _load_routes_from_brand_configs(self) -> List[Dict]:
        routes: List[Dict] = []
        registry = BrandRegistryService()
        for brand in registry.list_brands(active_only=False):
            brand_id = str(brand.get("brand_id") or "").strip()
            if not brand_id:
                continue
            config_root = registry.brand_config_root(brand_id)
            gsheet_file = config_root / "gsheet_settings.json"
            if not gsheet_file.exists():
                continue
            try:
                payload = json.loads(gsheet_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            configured_routes = payload.get("routes") or []
            if not isinstance(configured_routes, list):
                continue
            for route in configured_routes:
                if not isinstance(route, dict):
                    continue
                route_copy = dict(route)
                route_copy.setdefault("brand_id", brand_id)
                routes.append(route_copy)
        return routes

    def _authorize(self):
        """
        OAuth Desktop App authentication.

        Required file:
          secrets/google_oauth_client_secret.json

        First run:
          opens browser -> user logs in -> creates secrets/google_oauth_token.json

        Later runs:
          reuses token automatically.
        """
        if not Path(self.oauth_client_file).exists():
            raise FileNotFoundError(
                "Google OAuth client secret file not found: "
                f"{self.oauth_client_file}\n\n"
                "Create OAuth Client ID as a Desktop app in Google Cloud, "
                "download the JSON, rename it to google_oauth_client_secret.json, "
                "and put it under secrets/."
            )

        return gspread.oauth(
            credentials_filename=self.oauth_client_file,
            authorized_user_filename=self.oauth_token_file,
        )

    def _extract_spreadsheet_id(self, google_sheet_url: str) -> str:
        if not google_sheet_url:
            raise ValueError("google_sheet_url is empty.")
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", google_sheet_url)
        if match:
            return match.group(1)
        if "/" not in google_sheet_url and len(google_sheet_url) > 20:
            return google_sheet_url
        raise ValueError(f"Cannot extract spreadsheet ID from: {google_sheet_url}")

    def _find_route(
        self, brand_id: str, page_id: Optional[str], platform_id: Optional[str]
    ) -> Dict:
        active_routes = [
            r for r in self.routes if str(r.get("status", "active")).lower() == "active"
        ]
        for route in active_routes:
            if (
                route.get("brand_id") == brand_id
                and page_id
                and route.get("page_id") == page_id
                and (not platform_id or route.get("platform_id") == platform_id)
            ):
                return route
        for route in active_routes:
            if (
                route.get("brand_id") == brand_id
                and page_id
                and route.get("page_id") == page_id
            ):
                return route
        brand_platform_routes = [
            r
            for r in active_routes
            if r.get("brand_id") == brand_id
            and (not platform_id or r.get("platform_id") == platform_id)
        ]
        if len(brand_platform_routes) == 1:
            return brand_platform_routes[0]
        brand_routes = [r for r in active_routes if r.get("brand_id") == brand_id]
        if len(brand_routes) == 1:
            return brand_routes[0]
        raise ValueError(
            f"Cannot determine Google Sheet route. brand_id={brand_id}, page_id={page_id}, platform_id={platform_id}."
        )

    def _open_spreadsheet_for_route(self, route: Dict):
        spreadsheet_id = self._extract_spreadsheet_id(route.get("google_sheet_url"))
        return self.client.open_by_key(spreadsheet_id)

    def _get_or_create_worksheet(
        self, spreadsheet, title: str, rows: int = 1000, cols: int = 30
    ):
        try:
            return spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def _ensure_headers(self, worksheet, headers: List[str]):
        existing = worksheet.row_values(1)
        if existing[: len(headers)] == headers:
            return
        worksheet.update("A1", [headers])

    def _tab_name(self, route: Dict, key: str, default: str) -> str:
        return (route.get("tabs", {}) or {}).get(key) or default

    def _as_pipe_list(self, value):
        if value is None:
            return ""
        if isinstance(value, list):
            return "|".join([str(v) for v in value if v is not None])
        return str(value)

    def _ensure_headers_safe(self, worksheet, headers: List[str]):
        existing = worksheet.row_values(1)

        if not existing:
            worksheet.update("A1", [headers])
            return headers

        final_headers = list(existing)
        missing = [h for h in headers if h not in final_headers]

        if missing:
            start_col = len(final_headers) + 1
            final_headers.extend(missing)
            worksheet.update("A1", [final_headers])

        return final_headers

    def _append_records_by_headers(
        self, worksheet, records: List[Dict], required_headers: List[str]
    ) -> int:
        if not records:
            return 0

        current_headers = self._ensure_headers_safe(worksheet, required_headers)

        rows = [
            [record.get(header, "") for header in current_headers] for record in records
        ]

        worksheet.append_rows(
            rows,
            value_input_option="USER_ENTERED",
            table_range="A1",
        )

        return len(rows)

    def _rows_to_records(self, values: List[List[str]]) -> List[Dict]:
        if not values:
            return []
        headers = [str(h or "").strip() for h in values[0]]
        records = []
        for row_number, row_values in enumerate(values[1:], start=2):
            record = {"__row_number__": row_number}
            for idx, header in enumerate(headers):
                if not header:
                    continue
                record[header] = row_values[idx] if idx < len(row_values) else ""
            if any(str(v or "").strip() for k, v in record.items() if not k.startswith("__")):
                records.append(record)
        return records

    def _worksheet_records(self, worksheet) -> List[Dict]:
        return self._rows_to_records(worksheet.get_all_values())

    def _index_existing_rows(self, worksheet, headers: List[str], key_fields: List[str]) -> Dict:
        rows = self._worksheet_records(worksheet)
        indexed = {}
        for row in rows:
            key = tuple(str(row.get(field, "") or "").strip() for field in key_fields)
            if all(key):
                indexed[key] = row
        return indexed

    def _update_row_fields(self, worksheet, row_number: int, headers: List[str], record: Dict) -> None:
        header_index = {header: idx + 1 for idx, header in enumerate(headers)}
        updates = []
        for key, value in record.items():
            if key not in header_index:
                continue
            col = header_index[key]
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_number, col),
                "values": [[value]],
            })
        if updates:
            worksheet.batch_update(updates, value_input_option="USER_ENTERED")

    def _upsert_records_by_keys(
        self,
        worksheet,
        records: List[Dict],
        required_headers: List[str],
        key_fields: List[str],
    ) -> Dict:
        if not records:
            return {"appended": 0, "updated": 0}
        headers = self._ensure_headers_safe(worksheet, required_headers)
        existing = self._index_existing_rows(worksheet, headers, key_fields)
        append_rows = []
        updated = 0
        appended = 0

        for record in records:
            key = tuple(str(record.get(field, "") or "").strip() for field in key_fields)
            if all(key) and key in existing:
                row_number = int(existing[key]["__row_number__"])
                self._update_row_fields(worksheet, row_number, headers, record)
                updated += 1
            else:
                append_rows.append([record.get(header, "") for header in headers])
                appended += 1

        if append_rows:
            worksheet.append_rows(
                append_rows,
                value_input_option="USER_ENTERED",
                table_range="A1",
            )

        return {"appended": appended, "updated": updated}

    def upsert_organic_results(self, route: Dict, records: List[Dict]) -> Dict:
        spreadsheet = self._open_spreadsheet_for_route(route)
        results_tab = self._tab_name(route, "results", "Organic_Results")
        ws = self._get_or_create_worksheet(
            spreadsheet,
            results_tab,
            rows=1000,
            cols=max(len(self.ORGANIC_RESULTS_HEADERS), 30),
        )
        stats = self._upsert_records_by_keys(
            worksheet=ws,
            records=records,
            required_headers=self.ORGANIC_RESULTS_HEADERS,
            key_fields=["date", "facebook_post_id"],
        )
        return {
            "spreadsheet_title": spreadsheet.title,
            "tab": results_tab,
            **stats,
        }

    def _normalize_daily_learning_headers(self, worksheet) -> List[str]:
        existing = worksheet.row_values(1)
        if existing.count("weak_content_roles_ai") >= 2 and "weak_pillars_ai" not in existing:
            seen = 0
            fixed = []
            for header in existing:
                if header == "weak_content_roles_ai":
                    seen += 1
                    fixed.append("weak_pillars_ai" if seen == 2 else header)
                else:
                    fixed.append(header)
            worksheet.update("A1", [fixed])
        return self._ensure_headers_safe(worksheet, self.DAILY_LEARNING_HEADERS)

    def upsert_daily_learning_logs(self, route: Dict, records: List[Dict]) -> Dict:
        spreadsheet = self._open_spreadsheet_for_route(route)
        learning_tab = self._tab_name(route, "learning", "Daily_Learning_Log")
        ws = self._get_or_create_worksheet(
            spreadsheet,
            learning_tab,
            rows=1000,
            cols=max(len(self.DAILY_LEARNING_HEADERS), 30),
        )
        self._normalize_daily_learning_headers(ws)
        stats = self._upsert_records_by_keys(
            worksheet=ws,
            records=records,
            required_headers=self.DAILY_LEARNING_HEADERS,
            key_fields=["date", "brand_id", "page_id", "platform_id", "campaign_id"],
        )
        return {
            "spreadsheet_title": spreadsheet.title,
            "tab": learning_tab,
            **stats,
        }

    def _extract_reaction_prediction(self, post: Dict) -> Dict:
        prediction = post.get("reaction_prediction", {}) or {}

        if isinstance(prediction, str):
            return {
                "expected_primary_reaction": prediction,
                "why_people_would_like": prediction,
                "why_people_would_comment": "",
                "why_people_would_share": "",
                "possible_light_disagreement": "",
            }

        if not isinstance(prediction, dict):
            prediction = {}

        return {
            "expected_primary_reaction": (
                prediction.get("expected_primary_reaction")
                or prediction.get("primary_reaction")
                or prediction.get("reaction")
                or ""
            ),
            "why_people_would_like": (
                prediction.get("why_people_would_like")
                or prediction.get("why_like")
                or prediction.get("like_reason")
                or ""
            ),
            "why_people_would_comment": (
                prediction.get("why_people_would_comment")
                or prediction.get("why_comment")
                or prediction.get("comment_reason")
                or ""
            ),
            "why_people_would_share": (
                prediction.get("why_people_would_share")
                or prediction.get("why_share")
                or prediction.get("share_reason")
                or ""
            ),
            "possible_light_disagreement": (
                prediction.get("possible_light_disagreement")
                or prediction.get("light_disagreement")
                or prediction.get("possible_disagreement")
                or ""
            ),
        }

    def _extract_campaign_kpi_influence(
        self, post: Dict, campaign_kpi_context: Optional[Dict]
    ) -> Dict:
        value = post.get("campaign_kpi_influence", {}) or {}
        if value:
            return value

        campaign_kpi_context = campaign_kpi_context or {}
        return {
            "kpi_status": campaign_kpi_context.get("kpi_status", ""),
            "content_intensity": campaign_kpi_context.get("content_intensity", ""),
            "why_this_post_fits_kpi": campaign_kpi_context.get(
                "generation_instruction", ""
            ),
        }

    def _post_to_record(
        self,
        organic_output: Dict,
        post: Dict,
        route: Dict,
        campaign_kpi_context: Optional[Dict] = None,
    ) -> Dict:
        prediction = self._extract_reaction_prediction(post)
        kpi = self._extract_campaign_kpi_influence(post, campaign_kpi_context)

        page_url = (
            organic_output.get("page_url")
            or route.get("page_url")
            or route.get("facebook_page_url")
            or ""
        )

        return {
            "campaign_id": organic_output.get("campaign_id"),
            "organic_run_id": organic_output.get("organic_run_id"),
            "post_id": post.get("post_id"),
            "created_at": organic_output.get("generated_at")
            or datetime.utcnow().isoformat(),
            "brand_id": organic_output.get("brand_id") or route.get("brand_id"),
            "niche_id": organic_output.get("niche_id") or route.get("niche_id"),
            "page_id": organic_output.get("page_id") or route.get("page_id"),
            "platform_id": organic_output.get("platform_id")
            or route.get("platform_id"),
            "page_url": page_url,
            "content_archetype": post.get("content_archetype"),
            "interaction_trigger_type": post.get("interaction_trigger_type"),
            "target_human": post.get("target_human"),
            "current_emotional_state": post.get("current_emotional_state"),
            "core_problem": post.get("core_problem"),
            "core_solution": post.get("core_solution"),
            "primary_takeaway": post.get("primary_takeaway"),
            "desired_post_outcome": post.get("desired_post_outcome"),
            "desired_action": post.get("desired_action"),
            "awareness_stage": post.get("awareness_stage"),
            "planned_publish_day": post.get("planned_publish_day"),
            "current_followers_snapshot": post.get("current_followers_snapshot")
            or campaign_kpi_context.get("current_followers", ""),
            "current_likes_snapshot": post.get("current_likes_snapshot")
            or campaign_kpi_context.get("current_likes", ""),
            "post_format": post.get("post_format"),
            "content_role": post.get("content_role"),
            "content_pillar": post.get("content_pillar"),
            "angle_used": post.get("angle_used"),
            "hook_type": post.get("hook_type"),
            "product_mention_level": post.get("product_mention_level"),
            "hook": post.get("hook"),
            "post_text": post.get("post_text"),
            "engagement_prompt": post.get("engagement_prompt"),
            "chatgpt_image_prompt": post.get("chatgpt_image_prompt"),
            "content_tags": self._as_pipe_list(post.get("content_tags")),
            "seo_keywords_used": self._as_pipe_list(post.get("seo_keywords_used")),
            "brand_keywords_used": self._as_pipe_list(post.get("brand_keywords_used")),
            "trend_keywords_used": self._as_pipe_list(post.get("trend_keywords_used")),
            "platform_native_keywords": self._as_pipe_list(
                post.get("platform_native_keywords")
            ),
            "expected_primary_reaction": prediction.get("expected_primary_reaction"),
            "why_people_would_like": prediction.get("why_people_would_like"),
            "why_people_would_comment": prediction.get("why_people_would_comment"),
            "why_people_would_share": prediction.get("why_people_would_share"),
            "possible_light_disagreement": prediction.get(
                "possible_light_disagreement"
            ),
            "image_intent": post.get("image_intent"),
            "product_reference_required": post.get("product_reference_required"),
            "product_reference_note": post.get("product_reference_note"),
            "image_url": post.get("image_url", ""),
            "recommended_posting_window": post.get("recommended_posting_window"),
            "behavioral_reason": post.get("behavioral_reason"),
            "historical_confidence": post.get("historical_confidence"),
            "scheduled_datetime_utc": post.get("scheduled_datetime_utc"),
            "campaign_kpi_status": kpi.get("kpi_status"),
            "campaign_content_intensity": kpi.get("content_intensity"),
            "why_this_post_fits_kpi": kpi.get("why_this_post_fits_kpi"),
            "post_status": "draft",
            "publisher_status": "",
            "facebook_post_id": "",
            "publisher_error": "",
            "published_or_scheduled_at": "",
            "notes_user": "",
        }

    def _ensure_base_tabs(self, spreadsheet, route: Dict) -> Dict:
        posts_tab = self._tab_name(route, "posts", "Organic_Posts")
        results_tab = self._tab_name(route, "results", "Organic_Results")
        learning_tab = self._tab_name(route, "learning", "Daily_Learning_Log")
        pages_tab = self._tab_name(route, "pages", "Page_Channel_Library")
        brand_tab = self._tab_name(route, "brand_config", "Brand_Config")

        tabs = [
            (posts_tab, self.ORGANIC_POSTS_HEADERS, 1000),
            (results_tab, self.ORGANIC_RESULTS_HEADERS, 1000),
            (learning_tab, self.DAILY_LEARNING_HEADERS, 1000),
        ]

        worksheets = {}
        for title, headers, rows in tabs:
            ws = self._get_or_create_worksheet(
                spreadsheet, title, rows=rows, cols=max(len(headers), 30)
            )
            self._ensure_headers(ws, headers)
            worksheets[title] = ws

        return worksheets

    def export_organic_posts(
        self,
        organic_output_file: str = "data/output/organic/organic_output.json",
        organic_output: Optional[Dict] = None,
        route: Optional[Dict] = None,
        campaign_kpi_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Export organic posts to Google Sheet.

        Backward compatible:
          export_organic_posts("data/output/organic/organic_output.json")

        New production service can call:
          export_organic_posts(organic_output=output, route=route, campaign_kpi_context=kpi)

        Behavior:
        - appends new rows
        - does not overwrite old rows
        - writes page_url
        - does not write post_url/published_date into Organic_Posts
        """

        if organic_output is None:
            organic_output_path = Path(organic_output_file)
            if not organic_output_path.exists():
                raise FileNotFoundError(
                    f"Organic output file not found: {organic_output_path}"
                )
            organic_output = json.loads(organic_output_path.read_text(encoding="utf-8"))

        brand_id = organic_output.get("brand_id")
        page_id = organic_output.get("page_id")
        platform_id = organic_output.get("platform_id")

        if not brand_id:
            raise ValueError("organic_output is missing brand_id.")

        if route is None:
            route = self._find_route(
                brand_id=brand_id, page_id=page_id, platform_id=platform_id
            )

        if campaign_kpi_context is None:
            campaign_kpi_context = organic_output.get("campaign_kpi_context", {}) or {}

        spreadsheet = self._open_spreadsheet_for_route(route)
        worksheets = self._ensure_base_tabs(spreadsheet, route)

        posts_tab = self._tab_name(route, "posts", "Organic_Posts")
        posts = (
            organic_output.get("organic_posts")
            or (organic_output.get("data", {}) or {}).get("organic_posts")
            or []
        )

        posts_ws = worksheets[posts_tab]
        current_headers = self._ensure_headers_safe(
            posts_ws,
            self.ORGANIC_POSTS_HEADERS,
        )

        records = [
            self._post_to_record(
                organic_output=organic_output,
                post=post,
                route=route,
                campaign_kpi_context=campaign_kpi_context,
            )
            for post in posts
        ]

        rows = [
            [record.get(header, "") for header in current_headers] for record in records
        ]

        if rows:
            if rows:
                posts_ws.append_rows(
                    rows,
                    value_input_option="USER_ENTERED",
                    table_range="A1",
                )

        return {
            "spreadsheet_title": spreadsheet.title,
            "spreadsheet_url": route.get("google_sheet_url"),
            "posts_tab": posts_tab,
            "rows_exported": len(rows),
            "rows_appended": len(rows),
            "organic_run_id": organic_output.get("organic_run_id"),
            "brand_id": brand_id,
            "page_id": page_id or route.get("page_id"),
            "platform_id": platform_id or route.get("platform_id"),
            "auth_mode": "oauth_user_login",
            "oauth_token_file": self.oauth_token_file,
        }
