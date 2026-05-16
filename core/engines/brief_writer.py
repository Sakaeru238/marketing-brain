import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class BriefWriter:
    def __init__(self):
        self.report_dir = PERFORMANCE_DIR / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build_brief(self, top_campaign, feedback_summary):
        if not top_campaign:
            return {"status": "no_campaign", "message": "No top campaign available."}

        return {
            "status": "ready",
            "campaign_id": top_campaign.get("campaign_id"),
            "campaign_name": top_campaign.get("campaign_name"),
            "objective": top_campaign.get("objective"),
            "angle": top_campaign.get("angle"),
            "primary_text": top_campaign.get("primary_text"),
            "headline": top_campaign.get("headline"),
            "cta": top_campaign.get("cta"),
            "ranking_score": top_campaign.get("ranking_score"),
            "prompts": top_campaign.get("prompts", {}),
            "best_objectives": feedback_summary.get("best_objectives", []),
            "best_skills": feedback_summary.get("best_skills", []),
        }

    def save(self, brief_data):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.report_dir / f"brief_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(brief_data, f, indent=2)

        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
        }
