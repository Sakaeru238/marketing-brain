import json
from datetime import datetime
from core.config.paths import PERFORMANCE_DIR


class ClaudeHandoffWriter:
    def __init__(self):
        # Thư mục lưu file handoff để đưa sang Claude / chat khác
        self.report_dir = PERFORMANCE_DIR / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build_refinement_prompt(self, claude_package_file, top_campaign):
        # Mode 1: Claude refine campaign tốt nhất
        # Dùng khi muốn Claude viết lại / tối ưu campaign
        return {
            "status": "ready",
            "mode": "claude_refinement",
            "instruction": (
                "You are continuing an AI Marketing Brain workflow. "
                "Read the attached claude package JSON, understand the best campaign, "
                "the top 3 campaigns, the feedback summary, and the briefs. "
                "Then improve the top campaign to make it more usable for real marketing execution."
            ),
            "task_requirements": [
                "Refine the top campaign angle",
                "Improve the primary text",
                "Improve the headline",
                "Suggest a stronger CTA",
                "Suggest how to test this campaign in practice",
                "Keep the output practical and money-oriented",
            ],
            "refinement_goals": [
                "Make the campaign clearer",
                "Make the campaign stronger for execution",
                "Make the campaign more persuasive",
                "Keep the campaign practical for real marketing use",
            ],
            "expected_output_format": {
                "top_campaign_v2": {
                    "campaign_name": "",
                    "objective": "",
                    "angle": "",
                    "primary_text": "",
                    "headline": "",
                    "cta": "",
                },
                "improvement_notes": [],
                "testing_suggestions": [],
            },
            "top_campaign_name": (
                top_campaign.get("campaign_name") if top_campaign else None
            ),
            "claude_package_file": claude_package_file,
        }

    def build_review_prompt(self, claude_package_file, top_campaign):
        # Mode 2: Claude review campaign tốt nhất
        # Dùng khi muốn Claude audit / phản biện / chấm điểm
        return {
            "status": "ready",
            "mode": "claude_review",
            "instruction": (
                "You are reviewing an AI Marketing Brain campaign package. "
                "Read the attached claude package JSON, evaluate the top campaign, "
                "and provide a practical review focused on real-world marketing execution."
            ),
            "task_requirements": [
                "Evaluate the top campaign angle",
                "Evaluate the primary text",
                "Evaluate the headline",
                "Evaluate the CTA",
                "Point out execution risks",
                "Suggest the most important improvements",
            ],
            "review_dimensions": [
                "Clarity",
                "Persuasiveness",
                "Execution readiness",
                "Testing readiness",
                "Practical business value",
            ],
            "expected_output_format": {
                "review_summary": "",
                "strengths": [],
                "weaknesses": [],
                "improvement_priorities": [],
                "execution_readiness_score": 0,
            },
            "top_campaign_name": (
                top_campaign.get("campaign_name") if top_campaign else None
            ),
            "claude_package_file": claude_package_file,
        }

    def build_execution_prompt(self, claude_package_file, top_campaign):
        # Mode 3: Claude chuyển campaign tốt nhất thành gói triển khai thực tế
        # Dùng khi muốn Claude đi xa hơn review/refine, tức là chuẩn bị cho launch/test thật
        return {
            "status": "ready",
            "mode": "claude_execution",
            "instruction": (
                "You are executing the next stage of an AI Marketing Brain workflow. "
                "Read the attached claude package JSON, take the top campaign, and turn it "
                "into a practical execution-ready marketing package."
            ),
            "task_requirements": [
                "Rewrite the top campaign into a launch-ready version",
                "Provide final primary text",
                "Provide final headline",
                "Provide final CTA",
                "Suggest 3 testing angles",
                "Suggest a simple execution plan",
                "Suggest a practical rollout sequence",
            ],
            "execution_goals": [
                "Make the campaign launch-ready",
                "Make the deliverable practical for a real team",
                "Make testing easier",
                "Keep output money-oriented and execution-oriented",
            ],
            "expected_output_format": {
                "launch_ready_campaign": {
                    "campaign_name": "",
                    "objective": "",
                    "angle": "",
                    "primary_text": "",
                    "headline": "",
                    "cta": "",
                },
                "testing_angles": [],
                "execution_plan": [],
                "rollout_sequence": [],
                "notes_for_team": [],
            },
            "top_campaign_name": (
                top_campaign.get("campaign_name") if top_campaign else None
            ),
            "claude_package_file": claude_package_file,
        }

    def save(self, handoff_data, prefix="claude_handoff"):
        # Lưu file handoff ra JSON riêng
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.report_dir / f"{prefix}_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(handoff_data, f, indent=2)

        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
        }
