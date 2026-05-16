import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class MultiBriefWriter:
    def __init__(self):
        self.report_dir = PERFORMANCE_DIR / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def save(self, multi_brief):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.report_dir / f"multi_brief_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(multi_brief, f, indent=2)

        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
        }
