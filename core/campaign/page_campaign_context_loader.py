from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.campaign.campaign_kpi_calculator import CampaignKPICalculator


class PageCampaignContextLoader:
    def __init__(self, exporter=None, calculator=None):
        self.exporter = exporter or GoogleSheetsExporter()
        self.calculator = calculator or CampaignKPICalculator()

    def load(self, brand_id="AODAI", page_id="AODAI_FB_US", platform_id="facebook"):
        route = self.exporter._find_route(brand_id, page_id, platform_id)
        spreadsheet = self.exporter._open_spreadsheet_for_route(route)
        tab = self.exporter._tab_name(route, "pages", "Page_Channel_Library")
        ws = spreadsheet.worksheet(tab)
        rows = ws.get_all_records()

        page_row = None
        for row in rows:
            if str(row.get("page_id", "")).strip() == page_id:
                page_row = row
                break

        if not page_row:
            raise ValueError(f"Page_Channel_Library row not found for page_id={page_id}")

        return {
            "route": route,
            "page_context": page_row,
            "campaign_kpi_context": self.calculator.calculate(page_row),
        }
