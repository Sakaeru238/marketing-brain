"""
Step 62B - Pipeline Evaluator

Mục tiêu:
- chấm nhanh output hiện tại
- kiểm tra xem learning đã ảnh hưởng campaign chưa
"""


class PipelineEvaluator:
    def evaluate_campaigns(self, campaigns):
        result = {
            "total_campaigns": len(campaigns),
            "has_scores": True,
            "top_score": 0,
            "average_score": 0,
        }

        if not campaigns:
            result["has_scores"] = False
            return result

        scores = []
        for campaign in campaigns:
            score = campaign.get("generator_score")
            if score is None:
                score = campaign.get("score_with_feedback")
            if score is None:
                score = campaign.get("score", 0)

            scores.append(score)

        result["top_score"] = max(scores) if scores else 0
        result["average_score"] = sum(scores) / len(scores) if scores else 0

        return result
