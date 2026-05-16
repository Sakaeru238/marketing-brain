"""
Step 58 - Generator Learning Adapter

Mục tiêu:
- Lấy feedback từ Step 57
- Tạo generator hints
- Feed vào campaign generator
"""

from datetime import datetime


class GeneratorLearningAdapter:

    def build_generator_hints(self, feedback_profile):
        """
        Convert feedback profile thành generator hints
        """

        hints = {
            "timestamp": datetime.utcnow().isoformat(),
            "preferred_angles": feedback_profile.get("preferred_angles", []),
            "preferred_ctas": feedback_profile.get("preferred_ctas", []),
            "preferred_audiences": feedback_profile.get("preferred_audiences", []),
            "preferred_formats": feedback_profile.get("preferred_formats", []),
        }

        return hints

    def apply_hints(self, campaigns, hints):
        """
        Apply hints vào campaigns
        """

        adjusted = []

        for campaign in campaigns:

            updated = dict(campaign)

            boost = 0

            # angle boost
            angle = str(updated).lower()

            for preferred in hints.get("preferred_angles", []):
                if preferred.lower() in angle:
                    boost += 2

            # cta boost
            for preferred in hints.get("preferred_ctas", []):
                if preferred.lower() in angle:
                    boost += 1

            updated["generator_boost"] = boost
            updated["generator_score"] = updated.get("score", 0) + boost

            adjusted.append(updated)

        adjusted.sort(key=lambda x: x.get("generator_score", 0), reverse=True)

        return adjusted
