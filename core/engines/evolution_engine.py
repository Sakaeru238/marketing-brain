"""
Step 59 - Auto Evolution Engine

Mục tiêu:
- nhận learning + feedback
- tạo evolution rules cho generator
- không sửa campaign generator cũ
"""

from datetime import datetime


class EvolutionEngine:
    def build_rules(self, learning, feedback_profile):
        """
        Build evolution rules từ learning + feedback.
        """

        rules = {
            "timestamp": datetime.utcnow().isoformat(),
            "preferred_angles": feedback_profile.get("preferred_angles", []),
            "preferred_ctas": feedback_profile.get("preferred_ctas", []),
            "preferred_audiences": feedback_profile.get("preferred_audiences", []),
            "preferred_formats": feedback_profile.get("preferred_formats", []),
            "generation_rules": [],
            "status": "ready",
        }

        for angle in feedback_profile.get("preferred_angles", []):
            rules["generation_rules"].append(
                {
                    "type": "angle_priority",
                    "value": angle,
                    "weight": 3,
                }
            )

        for cta in feedback_profile.get("preferred_ctas", []):
            rules["generation_rules"].append(
                {
                    "type": "cta_priority",
                    "value": cta,
                    "weight": 2,
                }
            )

        for audience in feedback_profile.get("preferred_audiences", []):
            rules["generation_rules"].append(
                {
                    "type": "audience_priority",
                    "value": audience,
                    "weight": 2,
                }
            )

        return rules
