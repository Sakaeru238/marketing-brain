from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import gspread
except Exception:  # pragma: no cover - handled at runtime
    gspread = None

from core.config.paths import GLOBAL_CONFIG_DIR
from core.services.brand_context_resolver import BrandContextResolver
from core.services.brand_registry_service import BrandRegistryService
from core.services.pod_cache_service import stable_hash
from .pod_pipeline_utils import read_json, safe_name, utc_now, write_json


class PodInputResolver:
    """
    Resolves POD campaign inputs from brand_id using configured Google Sheets.

    Campaign source rule:
    - read config/brands/{brand_id}/gsheet_settings.json
    - read modules.pod.campaign.google_sheet_url
    - read tab names/fields from config/global/gsheet_schema.json
    - process only campaign rows where status == ready
    - update the same row as the campaign advances
    """

    def __init__(
        self,
        *,
        registry_service: BrandRegistryService | None = None,
        oauth_client_file: str | None = None,
        oauth_token_file: str | None = None,
    ) -> None:
        self.registry_service = registry_service or BrandRegistryService()
        self.context_resolver = BrandContextResolver(self.registry_service)
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

    def resolve_ready_campaign(
        self,
        *,
        brand_id: str,
        campaign_name: str | None = None,
    ) -> dict[str, Any]:
        paths = self.context_resolver.resolve(brand_id)
        brand_context = read_json(paths["brand_context_json_file"])
        brand_learning = read_json(paths["brand_learning_summary_file"], required=False)
        brand_snapshot_files = self._write_brand_source_snapshot(
            paths=paths,
            brand_context=brand_context,
            brand_learning=brand_learning,
        )

        source = self._load_campaign_source(brand_id)
        campaign_row = self._find_ready_campaign_row(
            rows=source["campaign_rows"],
            schema=source["schema"],
            campaign_name=campaign_name,
        )
        product_entry = self._find_product_entry(
            product_rows=source["product_rows"],
            schema=source["schema"],
            product_ref_id=campaign_row["data"].get("product_ref_id"),
        )

        resolved_campaign_id = safe_name(
            campaign_row["data"].get("campaign_id")
            or campaign_row["data"].get("campaign_name")
            or f"row_{campaign_row['row_number']}"
        )
        input_dir = (
            Path(paths["pod_root"])
            / "campaigns"
            / resolved_campaign_id
            / "00_inputs"
        )
        campaign_file = input_dir / "pod_campaign_intake.json"
        product_file = input_dir / "product_catalog_entry.json"
        source_snapshot_file = input_dir / "source_snapshot.json"
        write_json(campaign_file, campaign_row["data"])
        write_json(product_file, product_entry)
        write_json(
            source_snapshot_file,
            self._build_campaign_source_snapshot(
                brand_id=brand_id,
                campaign_id=resolved_campaign_id,
                campaign_row=campaign_row,
                product_entry=product_entry,
                source=source,
                brand_snapshot_files=brand_snapshot_files,
            ),
        )

        return {
            "brand_id": brand_id,
            "campaign_id": resolved_campaign_id,
            "brand_context": brand_context,
            "brand_learning": brand_learning,
            "campaign_intake": campaign_row["data"],
            "product_catalog_entry": product_entry,
            "source": {
                "spreadsheet_title": source["spreadsheet_title"],
                "google_sheet_url": source["google_sheet_url"],
                "campaign_tab": source["campaign_tab"],
                "product_catalog_tab": source["product_catalog_tab"],
                "campaign_row_number": campaign_row["row_number"],
                "status_column": source["status_column"],
                "url_column": source["url_column"],
            },
            "paths": {
                "brand_context_file": str(paths["brand_context_json_file"]),
                "brand_learning_file": str(paths["brand_learning_summary_file"])
                if Path(paths["brand_learning_summary_file"]).exists()
                else "",
                "brand_source_snapshot_file": str(brand_snapshot_files["brand_source_snapshot_file"]),
                "brand_context_snapshot_file": str(brand_snapshot_files["brand_context_snapshot_file"]),
                "brand_learning_snapshot_file": str(brand_snapshot_files["brand_learning_snapshot_file"])
                if brand_snapshot_files.get("brand_learning_snapshot_file")
                else "",
                "pod_campaign_intake_file": str(campaign_file),
                "product_catalog_entry_file": str(product_file),
                "source_snapshot_file": str(source_snapshot_file),
            },
        }

    def _build_campaign_source_snapshot(
        self,
        *,
        brand_id: str,
        campaign_id: str,
        campaign_row: dict[str, Any],
        product_entry: dict[str, Any],
        source: dict[str, Any],
        brand_snapshot_files: dict[str, Path | None],
    ) -> dict[str, Any]:
        campaign_schema = source["schema"]["campaign_intake"]
        campaign_hash_fields = campaign_schema.get("campaign_hash_fields") or []
        campaign_hash_payload = {
            field: campaign_row["data"].get(field, "")
            for field in campaign_hash_fields
        }
        product_schema = source["schema"]["product_catalog"]
        product_hash_fields = product_schema.get("product_hash_fields") or [product_schema["id_field"]]
        product_hash_payload = {
            field: product_entry.get(field, "")
            for field in product_hash_fields
        }
        return {
            "snapshot_type": "campaign_source_snapshot",
            "brand_id": brand_id,
            "campaign_id": campaign_id,
            "created_at": utc_now(),
            "source": {
                "spreadsheet_title": source["spreadsheet_title"],
                "google_sheet_url": source["google_sheet_url"],
                "campaign_tab": source["campaign_tab"],
                "campaign_row_number": campaign_row["row_number"],
                "product_catalog_tab": source["product_catalog_tab"],
            },
            "brand_snapshot_files": {
                key: str(value) if value else ""
                for key, value in brand_snapshot_files.items()
            },
            "hash_inputs": {
                "campaign_hash_fields": campaign_hash_fields,
                "campaign_intake_hash_payload": campaign_hash_payload,
                "product_hash_fields": product_hash_fields,
                "product_hash_payload": product_hash_payload,
            },
            "fingerprints": {
                "campaign_intake_hash": self._stable_hash(campaign_hash_payload),
                "product_catalog_entry_hash": self._stable_hash(product_hash_payload),
                "campaign_source_hash": self._stable_hash(
                    {
                        "campaign_intake_hash": self._stable_hash(campaign_hash_payload),
                        "product_catalog_entry_hash": self._stable_hash(product_hash_payload),
                    }
                ),
            },
        }

    def _write_brand_source_snapshot(
        self,
        *,
        paths: dict[str, Any],
        brand_context: dict[str, Any],
        brand_learning: dict[str, Any] | list[Any] | None,
    ) -> dict[str, Path | None]:
        cache_root = Path(paths["brand_data_root"]) / "cache" / "source"
        context_file = cache_root / "brand_context_snapshot.json"
        learning_file = cache_root / "brand_learning_snapshot.json"
        source_file = cache_root / "brand_source_snapshot.json"

        context_hash = self._stable_hash(brand_context)
        learning_hash = self._stable_hash(brand_learning or {})
        write_json(context_file, brand_context)
        if brand_learning is not None:
            write_json(learning_file, brand_learning)

        snapshot = {
            "snapshot_type": "brand_level_source_snapshot",
            "brand_id": paths["brand_id"],
            "created_at": utc_now(),
            "source_files": {
                "brand_context_file": str(paths["brand_context_json_file"]),
                "brand_learning_file": str(paths["brand_learning_summary_file"])
                if Path(paths["brand_learning_summary_file"]).exists()
                else "",
            },
            "snapshot_files": {
                "brand_context_snapshot_file": str(context_file),
                "brand_learning_snapshot_file": str(learning_file) if brand_learning is not None else "",
            },
            "fingerprints": {
                "brand_context_hash": context_hash,
                "brand_learning_hash": learning_hash,
                "brand_source_hash": self._stable_hash(
                    {
                        "brand_context_hash": context_hash,
                        "brand_learning_hash": learning_hash,
                    }
                ),
            },
        }
        write_json(source_file, snapshot)
        return {
            "brand_source_snapshot_file": source_file,
            "brand_context_snapshot_file": context_file,
            "brand_learning_snapshot_file": learning_file if brand_learning is not None else None,
        }

    def _stable_hash(self, payload: Any) -> str:
        return stable_hash(payload)

    def mark_campaign_status(
        self,
        *,
        brand_id: str,
        row_number: int,
        status: str,
        url: str | None = None,
    ) -> dict[str, Any]:
        source = self._load_campaign_source(brand_id)
        allowed = set(
            (source["schema"].get("campaign_intake") or {})
            .get("status_values", {})
            .keys()
        )
        if status not in allowed:
            raise ValueError(f"Invalid POD campaign status: {status}. Allowed={sorted(allowed)}")

        worksheet = source["campaign_worksheet"]
        worksheet.update_cell(row_number, source["status_column"], status)
        if url is not None:
            worksheet.update_cell(row_number, source["url_column"], url)
        return {
            "status": "success",
            "brand_id": brand_id,
            "row_number": row_number,
            "campaign_status": status,
            "url_updated": url is not None,
        }

    def _load_campaign_source(self, brand_id: str) -> dict[str, Any]:
        if gspread is None:
            raise RuntimeError("gspread is not available; cannot read POD campaign sheet.")

        brand = self.registry_service.get_brand(brand_id)
        if not self.registry_service.module_enabled(brand, "pod"):
            raise ValueError(f"Brand {brand_id} does not have enabled_modules.pod = true")

        config_root = self.registry_service.brand_config_root(brand_id)
        gsheet_file = config_root / "gsheet_settings.json"
        if not gsheet_file.exists():
            raise FileNotFoundError(f"Brand GSheet settings not found: {gsheet_file}")
        settings = json.loads(gsheet_file.read_text(encoding="utf-8"))
        pod_settings = ((settings.get("modules") or {}).get("pod") or {})
        campaign_settings = pod_settings.get("campaign") or pod_settings
        google_sheet_url = str(campaign_settings.get("google_sheet_url") or "").strip()
        schema_key = str(campaign_settings.get("schema_key") or pod_settings.get("schema_key") or "pod_campaign").strip()
        if not google_sheet_url:
            raise ValueError(f"Missing modules.pod.campaign.google_sheet_url in {gsheet_file}")

        schema = self._load_schema(schema_key)
        tabs = schema.get("tabs") or {}
        campaign_tab = tabs.get("campaign_intake")
        product_tab = tabs.get("product_catalog")
        if not campaign_tab or not product_tab:
            raise ValueError(f"Schema {schema_key} is missing campaign_intake/product_catalog tabs")

        if not Path(self.oauth_client_file).exists():
            raise FileNotFoundError(f"Google OAuth client secret not found: {self.oauth_client_file}")
        client = gspread.oauth(
            credentials_filename=self.oauth_client_file,
            authorized_user_filename=self.oauth_token_file,
        )
        spreadsheet = client.open_by_url(google_sheet_url)
        campaign_ws = spreadsheet.worksheet(campaign_tab)
        product_ws = spreadsheet.worksheet(product_tab)

        campaign_rows, campaign_headers = self._read_table(campaign_ws, schema["campaign_intake"]["header_required_columns"])
        product_rows, product_headers = self._read_table(product_ws, schema["product_catalog"]["header_required_columns"])

        status_field = schema["campaign_intake"]["status_field"]
        url_field = schema["campaign_intake"]["url_field"]
        return {
            "google_sheet_url": google_sheet_url,
            "spreadsheet_title": spreadsheet.title,
            "schema": schema,
            "campaign_tab": campaign_tab,
            "product_catalog_tab": product_tab,
            "campaign_worksheet": campaign_ws,
            "campaign_rows": campaign_rows,
            "product_rows": product_rows,
            "status_column": campaign_headers.index(status_field) + 1,
            "url_column": campaign_headers.index(url_field) + 1,
        }

    def _load_schema(self, schema_key: str) -> dict[str, Any]:
        schema_file = GLOBAL_CONFIG_DIR / "gsheet_schema.json"
        if not schema_file.exists():
            raise FileNotFoundError(f"GSheet schema config not found: {schema_file}")
        payload = json.loads(schema_file.read_text(encoding="utf-8"))
        schema = (payload.get("modules") or {}).get(schema_key) or {}
        if not schema:
            raise ValueError(f"GSheet schema module not found: {schema_key}")
        return schema

    def _read_table(self, worksheet, required_headers: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        values = worksheet.get_all_values()
        header_index = self._find_header_index(values, required_headers)
        headers = [str(value).strip() for value in values[header_index]]
        rows = []
        for row_number, row in enumerate(values[header_index + 1 :], start=header_index + 2):
            if not any(str(cell).strip() for cell in row):
                continue
            data = {}
            for index, header in enumerate(headers):
                if not header:
                    continue
                data[header] = str(row[index]).strip() if index < len(row) else ""
            rows.append({"row_number": row_number, "data": data})
        return rows, headers

    def _find_header_index(self, rows: list[list[Any]], required_headers: list[str]) -> int:
        required = {str(value).strip() for value in required_headers}
        for index, row in enumerate(rows[:20]):
            headers = {str(value).strip() for value in row}
            if required.issubset(headers):
                return index
        raise ValueError(f"Could not find header row containing required headers: {sorted(required)}")

    def _find_ready_campaign_row(
        self,
        *,
        rows: list[dict[str, Any]],
        schema: dict[str, Any],
        campaign_name: str | None,
    ) -> dict[str, Any]:
        status_field = schema["campaign_intake"]["status_field"]
        ready = []
        for item in rows:
            data = item["data"]
            if str(data.get(status_field) or "").strip().lower() != "ready":
                continue
            if campaign_name and str(data.get("campaign_name") or "").strip() != campaign_name:
                continue
            ready.append(item)
        if not ready:
            raise ValueError("No POD campaign row with status = ready was found.")
        if len(ready) > 1 and not campaign_name:
            raise ValueError(
                "Multiple POD campaign rows are ready. Pass a campaign name or leave only one row as ready."
            )
        return ready[0]

    def _find_product_entry(
        self,
        *,
        product_rows: list[dict[str, Any]],
        schema: dict[str, Any],
        product_ref_id: str | None,
    ) -> dict[str, Any]:
        id_field = schema["product_catalog"]["id_field"]
        wanted = str(product_ref_id or "").strip()
        if not wanted:
            raise ValueError("Ready POD campaign row is missing product_ref_id.")
        for item in product_rows:
            data = item["data"]
            if str(data.get(id_field) or "").strip() == wanted:
                return data
        raise ValueError(f"Product catalog entry not found for product_ref_id={wanted}")
