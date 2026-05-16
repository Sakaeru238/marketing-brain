import json
from core.exporters.google_sheets_exporter import GoogleSheetsExporter

def main():
    result = GoogleSheetsExporter().export_weekly_page_assessment()
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
