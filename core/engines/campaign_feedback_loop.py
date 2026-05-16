"""
Step 57 - Campaign Feedback Loop

Mục tiêu:
- nhận learning output từ Claude
- chuyển thành feedback profile có thể dùng lại
- áp feedback đó vào campaign ranking hoặc future generation

Nguyên tắc:
- không phá campaign generator cũ
- không đổi interface cũ
- chỉ bổ sung layer feedback
"""

from datetime import datetime
from pathlib import Path
import json


class CampaignFeedbackLoop:
    """
    Feedback loop giữa Claude learning và campaign system.
    """

    def __init__(self, save_dir="performance/learning"):
        """
        Parameters
        ----------
        save_dir : str
            Thư mục lưu feedback profile.
        """
        self.project_root = Path(__file__).resolve().parents[2]
        self.save_dir = self.project_root / save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------
    # BUILD FEEDBACK PROFILE
    # -----------------------------------------------------

    def build_feedback_profile(self, learning):
        """
        Chuẩn hóa learning result thành feedback profile.

        Parameters
        ----------
        learning : dict
            Output từ Step 56

        Returns
        -------
        dict
        """

        feedback_profile = {
            "timestamp": datetime.utcnow().isoformat(),
            "preferred_angles": learning.get("campaign_angles", []),
            "preferred_ctas": learning.get("cta_patterns", []),
            "preferred_audiences": learning.get("audience_patterns", []),
            "preferred_formats": learning.get("formats", []),
            "status": "ready",
        }

        return feedback_profile

    # -----------------------------------------------------
    # SCORE A SINGLE CAMPAIGN
    # -----------------------------------------------------

    def score_campaign_with_feedback(self, campaign, feedback_profile):
        """
        Tăng điểm cho campaign nếu campaign khớp learning signals.

        Parameters
        ----------
        campaign : dict
        feedback_profile : dict

        Returns
        -------
        dict
            Campaign đã được gắn feedback score
        """

        updated_campaign = dict(campaign)
        feedback_score = 0
        feedback_matches = []

        # Lấy text tổng hợp để match mềm, tránh phụ thuộc schema quá cứng
        campaign_text = " ".join(
            str(v).lower()
            for v in updated_campaign.values()
            if isinstance(v, (str, int, float))
        )

        # Angle matches
        for angle in feedback_profile.get("preferred_angles", []):
            if angle and str(angle).lower() in campaign_text:
                feedback_score += 3
                feedback_matches.append(f"angle:{angle}")

        # CTA matches
        for cta in feedback_profile.get("preferred_ctas", []):
            if cta and str(cta).lower() in campaign_text:
                feedback_score += 2
                feedback_matches.append(f"cta:{cta}")

        # Audience matches
        for audience in feedback_profile.get("preferred_audiences", []):
            if audience and str(audience).lower() in campaign_text:
                feedback_score += 2
                feedback_matches.append(f"audience:{audience}")

        updated_campaign["feedback_score"] = feedback_score
        updated_campaign["feedback_matches"] = feedback_matches

        # Giữ nguyên score cũ nếu có
        base_score = updated_campaign.get("score", 0)
        updated_campaign["score_with_feedback"] = base_score + feedback_score

        return updated_campaign

    # -----------------------------------------------------
    # APPLY FEEDBACK TO MULTIPLE CAMPAIGNS
    # -----------------------------------------------------

    def apply_feedback(self, campaigns, feedback_profile):
        """
        Áp feedback profile vào danh sách campaign.

        Parameters
        ----------
        campaigns : list[dict]
        feedback_profile : dict

        Returns
        -------
        list[dict]
            Danh sách campaign đã được feedback-adjusted
        """

        adjusted_campaigns = []

        for campaign in campaigns:
            adjusted = self.score_campaign_with_feedback(campaign, feedback_profile)
            adjusted_campaigns.append(adjusted)

        adjusted_campaigns.sort(
            key=lambda x: x.get("score_with_feedback", 0), reverse=True
        )

        return adjusted_campaigns

    # -----------------------------------------------------
    # SAVE FEEDBACK PROFILE
    # -----------------------------------------------------

    def save_feedback_profile(self, feedback_profile):
        """
        Save feedback profile ra file để trace/debug.

        Returns
        -------
        Path
        """

        filename = (
            f"campaign_feedback_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        file_path = self.save_dir / filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(feedback_profile, f, indent=2, ensure_ascii=False)

        return file_path
