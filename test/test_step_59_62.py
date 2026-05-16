import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.pipeline.master_pipeline import MasterPipeline


def test_step_59_62():
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
            "score": 9,
        },
        {
            "name": "Campaign C",
            "angle": "Vietnamese Coffee for Busy Mornings",
            "cta": "Shop Now",
            "score": 8,
        },
    ]

    print("=== EVOLUTION RULES ===")
    evolution_rules = pipeline.build_evolution_rules()
    print(evolution_rules)

    print("\n=== VALIDATION ===")
    validation_result = pipeline.validate_evolution_rules()
    print(validation_result["validation"])

    print("\n=== SNAPSHOT FILE ===")
    snapshot_file = pipeline.save_learning_snapshot()
    print(snapshot_file)

    print("\n=== GENERATOR LEARNING EVALUATION ===")
    evaluation_result = pipeline.evaluate_generator_learning(campaigns)
    print(evaluation_result["evaluation"])

    print("\n=== ADJUSTED CAMPAIGNS ===")
    for campaign in evaluation_result["adjusted_campaigns"]:
        print(campaign)


if __name__ == "__main__":
    test_step_59_62()
