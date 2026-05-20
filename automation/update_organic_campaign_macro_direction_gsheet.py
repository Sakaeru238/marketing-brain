import json
import sys
from pathlib import Path
from typing import List

import gspread

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config.paths import GLOBAL_CONFIG_DIR


def _spreadsheet_id(url: str) -> str:
    return url.split("/spreadsheets/d/", 1)[1].split("/", 1)[0]


def _column_letter(index_1_based: int) -> str:
    result = ""
    n = index_1_based
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _unique_macro_direction_options(direction_ws, source_field: str) -> List[str]:
    rows = direction_ws.get_all_records()
    return sorted({
        str(row.get(source_field) or "").strip()
        for row in rows
        if str(row.get(source_field) or "").strip()
    })


def main() -> None:
    brand_settings = json.loads(
        Path("config/brands/BRAND0001/gsheet_settings.json").read_text(encoding="utf-8")
    )
    schema = json.loads((GLOBAL_CONFIG_DIR / "gsheet_schema.json").read_text(encoding="utf-8"))

    organic_schema = schema["modules"]["organic"]
    route = brand_settings["routes"][0]
    tabs = {**organic_schema["tabs"], **route.get("tabs", {})}

    pages_tab = tabs["pages"]
    direction_tab = tabs["campaign_direction_library"]
    lists_tab = tabs["lists"]
    pages_schema = organic_schema["pages"]
    source_config = pages_schema["campaign_macro_direction_select_source"]

    target_column = pages_schema["campaign_macro_direction_field"]
    source_field = source_config["source_field"]
    list_header = source_config["lists_column_header"]

    client = gspread.oauth(
        credentials_filename="secrets/google_oauth_client_secret.json",
        authorized_user_filename="secrets/google_oauth_token.json",
    )
    spreadsheet = client.open_by_key(_spreadsheet_id(route["google_sheet_url"]))
    pages_ws = spreadsheet.worksheet(pages_tab)
    direction_ws = spreadsheet.worksheet(direction_tab)

    headers = [str(value or "").strip() for value in pages_ws.row_values(1)]
    if target_column not in headers:
        if "campaign_id" not in headers:
            raise ValueError(f"{pages_tab} is missing campaign_id header.")
        insert_at = headers.index("campaign_id") + 2
        pages_ws.insert_cols([[target_column]], col=insert_at, value_input_option="USER_ENTERED")
        headers = [str(value or "").strip() for value in pages_ws.row_values(1)]
        target_column_index = headers.index(target_column) + 1
        source_column_index = max(target_column_index - 1, 1)
        spreadsheet.batch_update({
            "requests": [{
                "copyPaste": {
                    "source": {
                        "sheetId": pages_ws.id,
                        "startRowIndex": 0,
                        "endRowIndex": 1000,
                        "startColumnIndex": source_column_index - 1,
                        "endColumnIndex": source_column_index,
                    },
                    "destination": {
                        "sheetId": pages_ws.id,
                        "startRowIndex": 0,
                        "endRowIndex": 1000,
                        "startColumnIndex": target_column_index - 1,
                        "endColumnIndex": target_column_index,
                    },
                    "pasteType": "PASTE_FORMAT",
                    "pasteOrientation": "NORMAL",
                }
            }]
        })
        pages_ws.update_cell(1, target_column_index, target_column)
    else:
        target_column_index = headers.index(target_column) + 1

    options = _unique_macro_direction_options(direction_ws, source_field)
    if not options:
        raise ValueError(f"No options found in {direction_tab}.{source_field}.")

    try:
        lists_ws = spreadsheet.worksheet(lists_tab)
    except gspread.WorksheetNotFound:
        lists_ws = spreadsheet.add_worksheet(
            title=lists_tab,
            rows=max(len(options) + 5, 100),
            cols=20,
        )

    list_headers = [str(value or "").strip() for value in lists_ws.row_values(1)]
    if list_header in list_headers:
        list_column_index = list_headers.index(list_header) + 1
    else:
        list_column_index = len([header for header in list_headers if header]) + 1 if any(list_headers) else 1
        if list_column_index > lists_ws.col_count:
            lists_ws.add_cols(list_column_index - lists_ws.col_count)
        lists_ws.update_cell(1, list_column_index, list_header)

    list_column_letter = _column_letter(list_column_index)
    lists_ws.batch_clear([f"{list_column_letter}2:{list_column_letter}1000"])
    lists_ws.update(
        values=[[option] for option in options],
        range_name=f"{list_column_letter}2:{list_column_letter}{len(options) + 1}",
        value_input_option="USER_ENTERED",
    )

    spreadsheet.batch_update({
        "requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": lists_ws.id, "hidden": True},
                "fields": "hidden",
            }
        }]
    })

    validation_range = f"='{lists_tab}'!${list_column_letter}$2:${list_column_letter}${len(options) + 1}"
    spreadsheet.batch_update({
        "requests": [{
            "setDataValidation": {
                "range": {
                    "sheetId": pages_ws.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": target_column_index - 1,
                    "endColumnIndex": target_column_index,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_RANGE",
                        "values": [{"userEnteredValue": validation_range}],
                    },
                    "strict": True,
                    "showCustomUi": True,
                },
            }
        }]
    })

    print(json.dumps({
        "status": "success",
        "spreadsheet": spreadsheet.title,
        "campaign_config_tab": pages_tab,
        "column": target_column,
        "column_index": target_column_index,
        "source_tab": direction_tab,
        "source_field": source_field,
        "options_count": len(options),
        "options": options,
        "lists_tab": lists_tab,
        "lists_header": list_header,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
