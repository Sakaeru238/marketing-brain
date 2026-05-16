import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class ClaudeProWriter:
    def __init__(self):
        # Thư mục lưu file handoff dành riêng cho Claude Pro
        self.report_dir = PERFORMANCE_DIR / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build_package(
        self,
        top_campaign,
        top_campaigns,
        brief_data,
        multi_brief,
        feedback_summary,
        claude_execution,
    ):
        # Package này tối ưu cho workflow thủ công với Claude Pro:
        # - upload file JSON
        # - copy prompt vào Claude
        # - Claude tiếp tục refine / execute
        return {
            "status": "ready_for_claude_pro",
            "use_mode": "manual_upload",
            "recommended_workflow": [
                "Upload this JSON file into Claude Pro",
                "Paste the prompt from claude_execution or claude_handoff",
                "Ask Claude to continue from this package only",
                "Request practical, execution-ready output"
            ],
            "top_campaign": top_campaign,
            "top_campaigns": top_campaigns,
            "brief": brief_data,
            "multi_brief": multi_brief,
            "feedback_summary": feedback_summary,
            "claude_execution_prompt": claude_execution,
        }

    def save(self, data):
        # Lưu file package cho Claude Pro
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.report_dir / f"claude_pro_package_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
        }