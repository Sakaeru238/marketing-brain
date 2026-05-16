import json

from core.exporters.google_sheets_exporter import GoogleSheetsExporter

ORGANIC_OUTPUT_FILE = "data/output/organic/organic_output.json"
ROUTING_FILE = "config/google_sheet_routing.json"


def main():
    exporter = GoogleSheetsExporter(routing_file=ROUTING_FILE)
    result = exporter.export_organic_posts(organic_output_file=ORGANIC_OUTPUT_FILE)
    print("\n====== EXPORT ORGANIC TO GOOGLE SHEET ======\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
