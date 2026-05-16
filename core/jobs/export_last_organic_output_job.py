from dotenv import load_dotenv

load_dotenv()

import json

from core.exporters.google_sheets_exporter import GoogleSheetsExporter
from core.notifications.telegram_notifier import TelegramNotifier


def main():
    notifier = TelegramNotifier()
    exporter = GoogleSheetsExporter()

    result = exporter.export_organic_posts(
        organic_output_file="data/output/organic/organic_output.json"
    )

    notifier.send(
        "✅ Last organic output exported to Google Sheet\n"
        f"Sheet: {result.get('spreadsheet_title')}\n"
        f"Tab: {result.get('posts_tab')}\n"
        f"Rows appended: {result.get('rows_appended') or result.get('rows_exported')}"
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
