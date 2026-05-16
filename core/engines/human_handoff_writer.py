import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class HumanHandoffWriter:
    def __init__(self):
        # Thư mục lưu file handoff cho người thật trong team
        self.report_dir = PERFORMANCE_DIR / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build_package(
        self,
        top_campaign,
        top_campaigns,
        feedback_summary,
        brief_data,
    ):
        # Package này tối ưu cho người đọc:
        # - ngắn
        # - rõ
        # - tập trung vào thứ cần hành động
        if not top_campaign:
            return {"status": "no_campaign", "message": "No top campaign available."}

        return {
            "status": "ready_for_human",
            "summary": {
                "best_objectives": feedback_summary.get("best_objectives", []),
                "best_skills": feedback_summary.get("best_skills", []),
                "total_experiments": feedback_summary.get("total_experiments", 0),
            },
            "claude_recommended_mode": "Use Claude Pro manual workflow first. Switch to Claude API when cost control is ready.",
            "top_campaign": {
                "campaign_name": top_campaign.get("campaign_name"),
                "objective": top_campaign.get("objective"),
                "angle": top_campaign.get("angle"),
                "primary_text": top_campaign.get("primary_text"),
                "headline": top_campaign.get("headline"),
                "cta": top_campaign.get("cta"),
                "ranking_score": top_campaign.get("ranking_score"),
            },
            "top_3_campaigns": [
                {
                    "campaign_name": campaign.get("campaign_name"),
                    "objective": campaign.get("objective"),
                    "angle": campaign.get("angle"),
                    "headline": campaign.get("headline"),
                    "cta": campaign.get("cta"),
                    "ranking_score": campaign.get("ranking_score"),
                }
                for campaign in top_campaigns
            ],
            "best_brief": brief_data,
            "recommended_next_actions": [
                "Review the top campaign first",
                "Compare the top 3 campaigns",
                "Choose one for immediate test",
                "Prepare creative assets based on prompts",
                "Launch a small test before scaling",
            ],
        }

    def save(self, handoff_data):
        # Lưu file handoff cho người thật
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.report_dir / f"human_handoff_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(handoff_data, f, indent=2)

        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
        }
