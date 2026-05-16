from dotenv import load_dotenv
load_dotenv()

import json
from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.utils.campaign_kpi_calculator import CampaignKPICalculator


def main():
    exporter = GoogleSheetsExporter()
    route = exporter._find_route(
        brand_id="AODAI",
        page_id="AODAI_FB_US",
        platform_id="facebook",
    )

    spreadsheet = exporter._open_spreadsheet_for_route(route)
    tab = exporter._tab_name(route, "pages", "Page_Channel_Library")
    ws = spreadsheet.worksheet(tab)

    rows = ws.get_all_records()
    target = None

    for row in rows:
        if row.get("page_id") == "AODAI_FB_US":
            target = row
            break

    if not target:
        raise ValueError("Page row not found: AODAI_FB_US")

    result = CampaignKPICalculator().calculate(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
