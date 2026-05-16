import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class ClaudePackageWriter:
    def __init__(self):
        # Thư mục lưu package để handoff sang Claude/chat khác
        self.report_dir = PERFORMANCE_DIR / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build_package(
        self,
        top_campaign,
        top_campaigns,
        feedback_summary,
        brief_data,
        multi_brief,
    ):
        # Gói dữ liệu sạch, tập trung vào thứ Claude cần để tiếp tục tối ưu
        return {
            "status": "ready_for_claude",
            "top_campaign": top_campaign,
            "top_campaigns": top_campaigns,
            "feedback_summary": feedback_summary,
            "best_brief": brief_data,
            "multi_brief": multi_brief,
        }

    def save(self, package_data):
        # Lưu package ra file JSON riêng để dễ handoff
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.report_dir / f"claude_package_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(package_data, f, indent=2)

        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
        }
