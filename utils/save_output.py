import json
from pathlib import Path
from datetime import datetime


def save_output(parsed, stage_name, latest_filename):
    if not parsed:
        print(f"\n❌ {stage_name} output not saved because parsing failed.")
        return

    base_path = Path.cwd() / "data" / "output"

    latest_path = base_path / latest_filename
    history_path = (
        base_path
        / "history"
        / stage_name
        / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    latest_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    latest_path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    history_path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n✅ Saved latest: {latest_path}")
    print(f"📦 Saved history: {history_path}")
