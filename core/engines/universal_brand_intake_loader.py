import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

try:
    import gspread
except Exception:  # pragma: no cover - handled at runtime
    gspread = None

from core.services.brand_registry_service import BrandRegistryService


class UniversalBrandIntakeLoader:
    """Load universal Alysha brand intake responses from Excel or Google Sheets.

    Expected sheet layout is the field/value workbook created for universal brand
    intake. The loader is intentionally tolerant of title changes and searches for
    a header row containing `Field ID` and `Câu trả lời`.
    """

    REQUIRED_FIELDS = [
        "brand_name",
        "brand_website_url",
        "products_in_scope",
        "context_focus_scope",
        "known_brand_and_audience_context",
        "known_competitors",
        "known_brand_constraints",
        "existing_creative_or_messaging_to_remember",
    ]

    OPTIONAL_FIELD_ALIASES = {
        # Product catalog mapping evolved during design. Accept both names.
        "known_product_catalog": "known_product_catalog_sources",
        "known_product_catalog_sources": "known_product_catalog_sources",
        # Hero mapping evolved into notes + data source. Preserve old field as notes.
        "known_hero_product": "known_hero_product_notes",
        "known_hero_product_notes": "known_hero_product_notes",
        "hero_product_or_winner_design_source": "hero_product_or_winner_design_source",
    }

    DEFAULT_WORKSHEET_NAMES = [
        "01_Universal_Brand_Intake",
        "01_Brand_Intake",
        "01_POD_Brand_Intake",
    ]

    def __init__(
        self,
        *,
        brand_id: Optional[str] = None,
        excel_path: Optional[str] = None,
        worksheet_name: Optional[str] = None,
        gsheet_url: Optional[str] = None,
        registry_service: Optional[BrandRegistryService] = None,
        oauth_client_file: Optional[str] = None,
        oauth_token_file: Optional[str] = None,
    ):
        self.brand_id = str(brand_id or "").strip() or None
        self.excel_path = Path(excel_path) if excel_path else None
        self.worksheet_name = worksheet_name
        self.gsheet_url = gsheet_url
        self.registry_service = registry_service or BrandRegistryService()
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load(self) -> Dict[str, Any]:
        source = self._resolve_source()
        rows, source_meta = self._load_rows(source)
        field_rows = self._extract_field_rows(rows)
        normalized = self._normalize_field_rows(field_rows)
        validation = self._validate_required_fields(normalized)

        return {
            "brand_id": self.brand_id or normalized.get("brand_name") or "",
            "source": source_meta,
            "fields": normalized,
            "required_fields": list(self.REQUIRED_FIELDS),
            "validation": validation,
            "raw_field_rows": field_rows,
        }

    # ------------------------------------------------------------------
    # Source resolution
    # ------------------------------------------------------------------
    def _resolve_source(self) -> Dict[str, Any]:
        if self.excel_path:
            return {
                "source_type": "excel",
                "excel_path": str(self.excel_path),
                "worksheet_name": self.worksheet_name,
            }

        if self.gsheet_url:
            return {
                "source_type": "google_sheet",
                "google_sheet_url": self.gsheet_url,
                "worksheet_name": self.worksheet_name,
            }

        if not self.brand_id:
            raise ValueError("Provide --brand-id with configured GSheet, --input-xlsx, or --gsheet-url.")

        config_root = self.registry_service.brand_config_root(self.brand_id)
        gsheet_file = config_root / "gsheet_settings.json"
        if not gsheet_file.exists():
            raise FileNotFoundError(f"Brand GSheet settings not found: {gsheet_file}")
        payload = json.loads(gsheet_file.read_text(encoding="utf-8"))
        intake = payload.get("brand_intake") or {}
        if not intake:
            raise ValueError(f"Missing brand_intake block in {gsheet_file}")
        source_type = str(intake.get("source_type") or "google_sheet").strip().lower()
        if source_type == "excel":
            excel_path = intake.get("excel_path")
            if not excel_path:
                raise ValueError(f"brand_intake.excel_path is required in {gsheet_file}")
            return {
                "source_type": "excel",
                "excel_path": str(excel_path),
                "worksheet_name": self.worksheet_name or intake.get("worksheet_name"),
                "alternative_worksheet_names": intake.get("alternative_worksheet_names") or [],
                "config_file": str(gsheet_file),
            }
        google_sheet_url = intake.get("google_sheet_url")
        if not google_sheet_url:
            raise ValueError(
                f"brand_intake.google_sheet_url is empty in {gsheet_file}. "
                "Paste the brand-specific intake sheet URL or use --input-xlsx."
            )
        return {
            "source_type": "google_sheet",
            "google_sheet_url": str(google_sheet_url),
            "worksheet_name": self.worksheet_name or intake.get("worksheet_name"),
            "alternative_worksheet_names": intake.get("alternative_worksheet_names") or [],
            "config_file": str(gsheet_file),
        }

    # ------------------------------------------------------------------
    # Source readers
    # ------------------------------------------------------------------
    def _load_rows(self, source: Dict[str, Any]) -> Tuple[List[List[Any]], Dict[str, Any]]:
        source_type = source.get("source_type")
        if source_type == "excel":
            return self._load_excel_rows(source)
        if source_type == "google_sheet":
            return self._load_google_sheet_rows(source)
        raise ValueError(f"Unsupported intake source_type: {source_type}")

    def _load_excel_rows(self, source: Dict[str, Any]) -> Tuple[List[List[Any]], Dict[str, Any]]:
        path = Path(str(source.get("excel_path") or ""))
        if not path.exists():
            raise FileNotFoundError(f"Universal Brand Intake Excel not found: {path}")

        xls = pd.ExcelFile(path)
        sheet_name = self._choose_sheet_name(
            available=xls.sheet_names,
            requested=source.get("worksheet_name"),
            alternatives=source.get("alternative_worksheet_names") or [],
        )
        df = pd.read_excel(path, sheet_name=sheet_name, header=None)
        df = df.where(pd.notnull(df), "")
        rows = df.values.tolist()
        return rows, {
            "source_type": "excel",
            "path": str(path),
            "worksheet_name": sheet_name,
            "config_file": source.get("config_file"),
        }

    def _load_google_sheet_rows(self, source: Dict[str, Any]) -> Tuple[List[List[Any]], Dict[str, Any]]:
        if gspread is None:
            raise RuntimeError("gspread is not available; cannot read Google Sheets intake.")
        if not Path(self.oauth_client_file).exists():
            raise FileNotFoundError(f"Google OAuth client secret not found: {self.oauth_client_file}")
        client = gspread.oauth(
            credentials_filename=self.oauth_client_file,
            authorized_user_filename=self.oauth_token_file,
        )
        spreadsheet = client.open_by_url(str(source.get("google_sheet_url")))
        available = [ws.title for ws in spreadsheet.worksheets()]
        sheet_name = self._choose_sheet_name(
            available=available,
            requested=source.get("worksheet_name"),
            alternatives=source.get("alternative_worksheet_names") or [],
        )
        worksheet = spreadsheet.worksheet(sheet_name)
        rows = worksheet.get_all_values()
        return rows, {
            "source_type": "google_sheet",
            "google_sheet_url": str(source.get("google_sheet_url")),
            "worksheet_name": sheet_name,
            "config_file": source.get("config_file"),
        }

    def _choose_sheet_name(self, *, available: Iterable[str], requested: Optional[str], alternatives: Iterable[str]) -> str:
        available_list = list(available)
        candidates = []
        for name in [requested, *list(alternatives or []), *self.DEFAULT_WORKSHEET_NAMES]:
            if not name:
                continue
            name = str(name)
            if name not in candidates:
                candidates.append(name)
        for candidate in candidates:
            if candidate in available_list:
                return candidate
        if len(available_list) == 1:
            return available_list[0]
        raise ValueError(f"Could not determine intake worksheet. Available={available_list}, candidates={candidates}")

    # ------------------------------------------------------------------
    # Layout parsing
    # ------------------------------------------------------------------
    def _extract_field_rows(self, rows: List[List[Any]]) -> List[Dict[str, Any]]:
        header_index, headers = self._find_header_row(rows)
        if header_index is None:
            raise ValueError("Could not find intake header row containing Field ID and Câu trả lời.")

        header_map = {self._normalize_header(value): idx for idx, value in enumerate(headers)}
        field_col = header_map.get("field id")
        answer_col = header_map.get("câu trả lời")
        question_col = header_map.get("câu hỏi / trường intake")
        level_col = header_map.get("mức độ")
        group_col = header_map.get("nhóm")

        parsed: List[Dict[str, Any]] = []
        for row in rows[header_index + 1 :]:
            if not isinstance(row, list):
                row = list(row)
            field_id = self._safe_cell(row, field_col)
            if not field_id:
                continue
            parsed.append(
                {
                    "field_id": field_id,
                    "answer": self._safe_cell(row, answer_col),
                    "question": self._safe_cell(row, question_col),
                    "level": self._safe_cell(row, level_col),
                    "group": self._safe_cell(row, group_col),
                }
            )
        return parsed

    def _find_header_row(self, rows: List[List[Any]]) -> Tuple[Optional[int], List[Any]]:
        for idx, row in enumerate(rows[:30]):
            normalized = {self._normalize_header(value) for value in row}
            if "field id" in normalized and "câu trả lời" in normalized:
                return idx, row
        return None, []

    def _normalize_header(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def _safe_cell(self, row: List[Any], idx: Optional[int]) -> str:
        if idx is None or idx >= len(row):
            return ""
        value = row[idx]
        return str(value or "").strip()

    # ------------------------------------------------------------------
    # Field normalization / validation
    # ------------------------------------------------------------------
    def _normalize_field_rows(self, field_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for row in field_rows:
            original_id = str(row.get("field_id") or "").strip()
            if not original_id:
                continue
            canonical_id = self.OPTIONAL_FIELD_ALIASES.get(original_id, original_id)
            answer = str(row.get("answer") or "").strip()
            normalized[canonical_id] = answer
            if canonical_id != original_id:
                normalized.setdefault("_aliases", {})[original_id] = canonical_id
        return normalized

    def _validate_required_fields(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        missing = [field for field in self.REQUIRED_FIELDS if not str(fields.get(field) or "").strip()]
        return {
            "status": "pass" if not missing else "fail",
            "missing_required_fields": missing,
            "required_fields_total": len(self.REQUIRED_FIELDS),
            "required_fields_filled": len(self.REQUIRED_FIELDS) - len(missing),
        }
