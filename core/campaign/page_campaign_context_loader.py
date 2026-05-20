from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.campaign.campaign_kpi_calculator import CampaignKPICalculator



class PageCampaignContextLoader:
    def __init__(self, exporter=None, calculator=None):
        self.exporter = exporter or GoogleSheetsExporter()
        self.calculator = calculator or CampaignKPICalculator()

    def _normalize_key(self, value):
        return str(value or "").strip().casefold()

    def _load_campaign_direction_context(self, spreadsheet, route, page_row):
        macro_direction_name = str(page_row.get("campaign_macro_direction") or "").strip()
        result = {
            "campaign_macro_direction": macro_direction_name,
            "mapping_key": "Campaign_Config.campaign_macro_direction -> Campaign_Direction_Library.macro_direction_name",
            "match_status": "not_configured" if not macro_direction_name else "not_found",
            "direction_record": {},
        }
        if not macro_direction_name:
            return result
        tab = self.exporter._tab_name(route, "campaign_direction_library", "Campaign_Direction_Library")
        try:
            ws = spreadsheet.worksheet(tab)
            rows = ws.get_all_records()
        except Exception:
            return result
        target = self._normalize_key(macro_direction_name)
        for row in rows:
            if self._normalize_key(row.get("macro_direction_name")) == target:
                result["match_status"] = "matched"
                result["direction_record"] = dict(row or {})
                return result
        return result

    def load(self, brand_id="AODAI", page_id="AODAI_FB_US", platform_id="facebook", campaign_id=None):
        route = self.exporter._find_route(brand_id, page_id, platform_id)
        spreadsheet = self.exporter._open_spreadsheet_for_route(route)
        tab = self.exporter._tab_name(route, "pages", "Page_Channel_Library")
        ws = spreadsheet.worksheet(tab)
        rows = ws.get_all_records()

        page_row = None
        for row in rows:
            row = self.exporter.normalize_page_channel_record(row)
            row_brand_id = str(row.get("brand_id", "")).strip()
            row_page_id = str(row.get("page_id", "")).strip()
            row_platform_id = str(row.get("platform_id", "")).strip()
            row_campaign_id = str(row.get("campaign_id", "")).strip()
            if (
                row_brand_id == brand_id
                and row_page_id == page_id
                and row_platform_id == platform_id
                and (not campaign_id or row_campaign_id == campaign_id)
            ):
                page_row = row
                break

        if not page_row:
            raise ValueError(
                "Page_Channel_Library row not found for "
                f"brand_id={brand_id}, page_id={page_id}, platform_id={platform_id}, campaign_id={campaign_id or ''}"
            )

        campaign_kpi_context = self.calculator.calculate(page_row)
        campaign_direction_context = self._load_campaign_direction_context(spreadsheet, route, page_row)
        return {
            "route": route,
            "page_context": page_row,
            "campaign_kpi_context": campaign_kpi_context,
            "campaign_direction_context": campaign_direction_context,
        }
