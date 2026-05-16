import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.pipeline.master_pipeline import MasterPipeline


def test_step_57():
    pipeline = MasterPipeline()

    campaigns = [
        {
            "name": "Campaign A",
            "angle": "Vietnamese Coffee",
            "cta": "Shop Now",
            "score": 10,
        },
        {
            "name": "Campaign B",
            "angle": "Cold Brew Lifestyle",
            "cta": "Learn More",
            "score": 10,
        },
        {
            "name": "Campaign C",
            "angle": "Vietnamese Coffee for Busy People",
            "cta": "Shop Now",
            "score": 8,
        },
    ]

    result = pipeline.apply_campaign_feedback(campaigns)

    print("FEEDBACK PROFILE:")
    print(result["feedback_profile"])
    print("\nFEEDBACK FILE:")
    print(result["feedback_file"])
    print("\nADJUSTED CAMPAIGNS:")
    for campaign in result["adjusted_campaigns"]:
        print(campaign)


if __name__ == "__main__":
    test_step_57()
