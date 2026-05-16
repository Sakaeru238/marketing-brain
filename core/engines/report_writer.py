import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class ReportWriter:

    def __init__(self):
        self.report_dir = PERFORMANCE_DIR / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data):

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        file_path = self.report_dir / f"report_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return {"file_name": file_path.name, "file_path": str(file_path)}
