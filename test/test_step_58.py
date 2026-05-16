import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.pipeline.master_pipeline import MasterPipeline


def test_step_58():

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
            "angle": "Cold Brew",
            "cta": "Learn More",
            "score": 10,
        },
    ]

    result = pipeline.apply_generator_learning(campaigns)

    print("GENERATOR HINTS:")
    print(result["hints"])

    print("\nADJUSTED CAMPAIGNS:")
    for c in result["adjusted_campaigns"]:
        print(c)


if __name__ == "__main__":
    test_step_58()
